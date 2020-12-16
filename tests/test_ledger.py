"""Synthetic edge fixtures only; real snapshot checks are separate acceptance evidence."""
import csv
import io
import json
from pathlib import Path
import re
import shutil
import subprocess

from fastapi.testclient import TestClient
import pytest

from app.config import Settings, get_settings
from app.db import connect, initialize
from app.imports import FIELDS, ImportFailure, import_statement, parse_statement
from app.main import create_app
from app.money import MoneyError, parse_pennies


def statement(rows):
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(FIELDS)
    for row in rows:
        writer.writerow(row)
    return out.getvalue().encode()


def debit(date="01/01/2025", description="TEST BILL", amount="10.10", kind="DD"):
    return [date, kind, description, amount, "", "100.00"]


@pytest.fixture
def settings(tmp_path):
    value = Settings(str(tmp_path / "ledger.db"), 1_000_000, 50_000, 10)
    initialize(value.db_path)
    return value


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8280") as client:
        yield client


def test_exact_money_and_bad_formats():
    assert parse_pennies("0.29") + parse_pennies("0.01") == 30
    for bad in ["nan", "inf", "1e3", "1.001", "-1", "£1", "1,000", ""]:
        with pytest.raises(MoneyError):
            parse_pennies(bad)


def test_same_statement_idempotent_but_identical_rows_survive(settings):
    data = statement([debit(), debit()])
    assert import_statement(data, "demo.csv", settings)["inserted"] == 2
    assert import_statement(data, "renamed.csv", settings)["duplicates"] == 2
    with connect(settings.db_path) as db:
        assert db.execute("SELECT count(*),sum(amount_pence) FROM transactions").fetchone()[:] == (2, -2020)


@pytest.mark.parametrize("bad", [
    ["31/02/2025", "DD", "BILL", "1", "", "10"],
    ["01/01/2025", "DD", "BILL", "1", "1", "10"],
    ["01/01/2025", "DD", "BILL", "", "", "10"],
    ["01/01/2025", "DD", "BILL", "1.001", "", "10"],
    ["01/01/2025", "DD", "", "1", "", "10"],
])
def test_invalid_statement_atomic(settings, bad):
    with pytest.raises(ImportFailure):
        import_statement(statement([debit(), bad]), "bad.csv", settings)
    with connect(settings.db_path) as db:
        assert db.execute("SELECT count(*) FROM transactions").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM imports").fetchone()[0] == 0


def test_blank_type_credit_and_savings_do_not_disappear(client):
    data = statement([debit(description="SAVE THE CHANGE"), ["02/01/2025", "", "INTEREST", "", "0.29", "100"]])
    assert client.post('/api/imports', files={'file': ('test.csv', data)}).json()['blank_types'] == 1
    report = client.get('/api/summary?month=2025-01').json()
    assert (report['income_pence'], report['outflow_pence'], report['spending_pence'], report['transfers_pence']) == (29, 1010, 0, 1010)


def test_rule_priority_override_and_deletion(client):
    client.post('/api/imports', files={'file': ('test.csv', statement([debit(description="COFFEE")]))})
    low = client.post('/api/rules', json={'pattern': 'COFF', 'category': 'Dining', 'priority': 1}).json()
    high = client.post('/api/rules', json={'pattern': 'COFFEE', 'category': 'Housing', 'priority': 2}).json()
    row = client.get('/api/transactions').json()['items'][0]
    assert row['category'] == 'Housing'
    assert client.patch('/api/transactions/' + str(row['id']), json={'category': 'Groceries'}).json()['reason'] == 'Manual override'
    client.delete('/api/rules/' + str(high['id']))
    assert client.get('/api/transactions').json()['items'][0]['category'] == 'Groceries'
    client.patch('/api/transactions/' + str(row['id']), json={'category': None})
    assert client.get('/api/transactions').json()['items'][0]['category'] == 'Dining'
    assert low['id'] != high['id']


def test_recurrence_needs_dates_not_duplicate_rows(client):
    rows = [debit(d, 'MONTHLY BILL') for d in ['01/01/2025', '01/02/2025', '01/03/2025']]
    rows += [debit(description='SAME DAY')] * 4
    rows += [debit(d, 'IRREGULAR') for d in ['02/01/2025', '18/01/2025', '05/03/2025', '18/04/2025']]
    rows += [debit(d, 'SAVE THE CHANGE') for d in ['01/01/2025', '01/02/2025', '01/03/2025']]
    client.post('/api/imports', files={'file': ('test.csv', statement(rows))})
    candidates = client.get('/api/recurring').json()
    assert len(candidates) == 1
    assert candidates[0]['description'] == 'MONTHLY BILL'
    assert candidates[0]['cadence'] == 'monthly' and candidates[0]['observations'] == 3


def test_external_bank_transfers_count_as_spending_until_reviewed(client):
    client.post('/api/imports', files={'file': ('test.csv', statement([debit(kind='FPO')]))})
    report = client.get('/api/summary?month=2025-01').json()
    assert report['spending_pence'] == 1010 and report['transfers_pence'] == 0
    assert report['categories'][0]['category'] == 'Unreviewed transfers'


@pytest.mark.parametrize('dates,cadence', [
    (['01/01/2025', '08/01/2025', '15/01/2025'], 'weekly'),
    (['01/01/2023', '01/01/2024', '01/01/2025'], 'annual'),
])
def test_weekly_and_annual_cadence_with_small_amount_changes(client, dates, cadence):
    data = statement([debit(date, 'CADENCE BILL', amount) for date, amount in zip(dates, ['9.99', '10.20', '10.29'])])
    client.post('/api/imports', files={'file': ('test.csv', data)})
    candidates = client.get('/api/recurring').json()
    assert len(candidates) == 1 and candidates[0]['cadence'] == cadence
    assert candidates[0]['amount_pence'] == 1020


def test_budget_threshold_zero_and_persistence(client, settings):
    client.post('/api/imports', files={'file': ('test.csv', statement([debit(description='LIDL')]))})
    budget = {'month': '2025-01', 'category': 'Groceries', 'limit_pence': 2000, 'threshold_percent': 50}
    assert client.post('/api/budgets', json=budget).status_code == 200
    alert = client.get('/api/alerts?month=2025-01').json()[0]
    assert alert['spent_pence'] == 1010 and alert['state'] == 'warning'
    budget['limit_pence'] = 0
    client.post('/api/budgets', json=budget)
    assert client.get('/api/alerts?month=2025-01').json()[0]['state'] == 'over'
    initialize(settings.db_path)
    with TestClient(create_app(settings), base_url='http://127.0.0.1:8280') as reopened:
        assert reopened.get('/api/alerts?month=2025-01').json()[0]['limit_pence'] == 0
        assert reopened.get('/health').json()['transactions'] == 1


def test_local_boundary_size_and_query_validation(client):
    assert client.post('/api/rules', headers={'Origin': 'https://evil.example'}, json={}).status_code == 403
    assert client.post('/api/rules', headers={'Origin': 'null'}, json={}).status_code == 403
    assert client.get('/health', headers={'Host': 'evil.example'}).status_code == 400
    assert client.post('/api/imports', content=b'x' * 1_100_000).status_code == 413
    assert client.get('/api/summary?month=2025-13').status_code == 422
    assert client.get('/api/transactions?page=0').status_code == 422
    assert client.post('/api/budgets', json={'month': '2025-01', 'category': 'Other', 'limit_pence': 1.01}).status_code == 422
    assert "script-src 'self'" in client.get('/').headers['Content-Security-Policy']


def test_sql_text_and_html_are_data(client):
    malicious = "<img src=x onerror=alert(1)> '; DROP TABLE transactions;--"
    assert client.post('/api/imports', files={'file': ('test.csv', statement([debit(description=malicious)]))}).status_code == 200
    assert client.get('/api/transactions', params={'search': "'; DROP TABLE"}).json()['total'] == 1
    assert client.get('/health').json()['transactions'] == 1


def test_config_rejects_invalid_limits_and_currency(monkeypatch):
    monkeypatch.setenv('MONEYVIS_MAX_IMPORT_BYTES', '-1')
    with pytest.raises(ValueError):
        get_settings()
    monkeypatch.setenv('MONEYVIS_MAX_IMPORT_BYTES', '1000')
    monkeypatch.setenv('MONEYVIS_CURRENCY', 'USD')
    with pytest.raises(ValueError):
        get_settings()


def test_small_upload_rejects_truncation(settings):
    for data in [b'', b'no,valid,header\n', b'\xff\xfe']:
        with pytest.raises(ImportFailure):
            import_statement(data, 'bad.csv', settings)
    assert Path(settings.db_path).exists()


def test_schema_migration_preserves_custom_rules_and_overrides(settings):
    with connect(settings.db_path) as db:
        db.execute("UPDATE metadata SET value='1' WHERE key='schema'")
        db.execute("UPDATE rules SET category='Transfers',priority=800 WHERE id=5")
        db.execute("UPDATE rules SET category='Housing',priority=991 WHERE id=6")
    import_statement(statement([debit(kind='FPO')]), 'old.csv', settings)
    with connect(settings.db_path) as db:
        db.execute("UPDATE transactions SET override_category='Housing'")
    initialize(settings.db_path)
    with connect(settings.db_path) as db:
        assert db.execute("SELECT category,priority FROM rules WHERE id=5").fetchone()[:] == ('Unreviewed transfers', 20)
        assert db.execute("SELECT category,priority FROM rules WHERE id=6").fetchone()[:] == ('Housing', 991)
        assert db.execute("SELECT category,override_category FROM transactions").fetchone()[:] == ('Housing', 'Housing')


HEADER = ",".join(FIELDS)
ROW = "01/01/2025,DD,SYNTHETIC BILL,1.00,,10.00"


def stored_counts(settings):
    with connect(settings.db_path) as db:
        return tuple(db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("imports", "transactions"))


@pytest.mark.parametrize("newline", ["\r\n", "\r", "\n"])
def test_bom_line_endings_and_quoted_fields_keep_every_occurrence(settings, newline):
    quoted = '02/01/2025,DEB,"SYNTHETIC SHOP, UNIT 2\r\nLINE TWO",2.50,,-7.50'
    text = "\ufeff" + newline.join([HEADER, ROW, "", quoted, ROW]) + newline
    parsed, _ = parse_statement(text.encode(), settings)
    assert [r["row_number"] for r in parsed] == [1, 2, 3]
    assert parsed[1]["description"] == "SYNTHETIC SHOP, UNIT 2\r\nLINE TWO"
    assert [(r["amount_pence"], r["balance_pence"]) for r in parsed] == [(-100, 1000), (-250, -750), (-100, 1000)]


@pytest.mark.parametrize("text,message", [
    (HEADER + ",Balance\n" + ROW + ",1\n", "six documented"),
    (HEADER + ",\n" + ROW + ",\n", "six documented"),
    (HEADER + " \n" + ROW + "\n", "six documented"),
    (HEADER + "\n" + ROW + ",EXTRA\n", "column count"),
    (HEADER + "\n" + ROW + "\n01/01/2025,DD,SYNTHETIC BILL,1.00\n", "column count"),
    (HEADER + "\n" + ROW + "\n,,,,,\n", "does not match format"),
    (HEADER + "\n" + ROW + "\n01/01/2025,DD," + "X" * 3001 + ",1.00,,10.00\n", "too long"),
    (HEADER + "\n" + ROW + '\n01/01/2025,DD,"SYNTHETIC"X,1.00,,10.00\n', "expected after"),
    (HEADER + "\n" + ROW + '\n01/01/2025,DD,"SYNTHETIC,1.00,,10.00\n', "unexpected end of data"),
])
def test_malformed_structure_rejects_whole_statement(settings, text, message):
    with pytest.raises(ImportFailure) as failure:
        import_statement(text.encode(), "bad.csv", settings)
    assert any(message in d["error"] for d in failure.value.diagnostics)
    assert stored_counts(settings) == (0, 0)


@pytest.mark.parametrize("cells", [
    ["01/01/2025", "DD", "SYNTHETIC BILL", "\u0661\u0660.00", "", "10.00"],
    ["01/01/2025", "BGC", "SYNTHETIC PAY", "", "\uff11\uff10", "10.00"],
    ["01/01/2025", "DD", "SYNTHETIC BILL", "1.00", "", "\uff11\uff10"],
    ["01/01/2025", "DD", "SYNTHETIC BILL", "\u00a01.00", "", "10.00"],
    ["01/01/2025", "DD", "SYNTHETIC BILL", "1.00", "", "NaN"],
    ["01/01/2025", "DD", "SYNTHETIC BILL", "1.00", "", "-Infinity"],
    ["01/01/2025", "DD", "SYNTHETIC BILL", "1.00", "", "10.001"],
    ["01/01/2025", "DD", "SYNTHETIC BILL", "1.00", "", "--5.00"],
    ["01/01/2025", "DD", "SYNTHETIC BILL", "1.00", "", "-"],
    ["01/01/2025", "DD", "SYNTHETIC BILL", "1234567890123456", "", "10.00"],
])
def test_money_rejects_non_ascii_nonfinite_and_overprecision(settings, cells):
    with pytest.raises(ImportFailure):
        import_statement(statement([debit(), cells]), "bad.csv", settings)
    assert stored_counts(settings) == (0, 0)


def test_row_and_byte_bounds_are_inclusive(tmp_path):
    data = statement([debit(amount="90071992547409.91")] * 3)
    parsed, _ = parse_statement(data, Settings(str(tmp_path / "unused.db"), len(data), 3, 10))
    assert parsed[0]["amount_pence"] == -(2**53 - 1)
    for byte_limit, row_limit, message in [(len(data) - 1, 3, "byte limit"), (len(data), 2, "row limit")]:
        with pytest.raises(ImportFailure) as failure:
            parse_statement(data, Settings(str(tmp_path / "unused.db"), byte_limit, row_limit, 10))
        assert message in failure.value.diagnostics[0]["error"]


@pytest.mark.parametrize("amount,balance", [
    ("90071992547409.92", "1.00"),
    ("999999999999999.99", "1.00"),
    ("1.00", "-90071992547409.92"),
])
def test_amounts_outside_exact_integer_penny_range_are_rejected(settings, amount, balance):
    # 2**53 - 1 pennies is exact in SQLite int64 sums and JavaScript numbers alike.
    assert parse_pennies("90071992547409.91") == 2**53 - 1
    with pytest.raises(ImportFailure):
        import_statement(statement([debit(), debit(amount=amount)[:5] + [balance]]), "huge.csv", settings)
    assert stored_counts(settings) == (0, 0)


def test_hundred_maximum_debits_cannot_overflow_summaries(client):
    data = statement([debit(amount="999999999999999.99")] * 100)
    assert client.post('/api/imports', files={'file': ('max.csv', data)}).status_code == 400
    assert client.get('/api/summary?month=2025-01').json()['outflow_pence'] == 0


def test_gross_ledger_bound_is_cumulative_atomic_and_keeps_reimports(client, settings):
    limit = 2**53 - 1
    seed = statement([debit(amount="45035996273704.95"), ["02/01/2025", "BGC", "SYNTHETIC PAY", "", "45035996273704.95", "1.00"]])
    assert client.post('/api/imports', files={'file': ('seed.csv', seed)}).json()['inserted'] == 2
    assert stored_counts(settings) == (1, 2)
    over = client.post('/api/imports', files={'file': ('over.csv', statement([debit(amount="0.02")]))})
    assert over.status_code == 400 and 'gross ledger' in over.json()['diagnostics'][0]['error']
    assert stored_counts(settings) == (1, 2)
    assert client.post('/api/imports', files={'file': ('seed.csv', seed)}).json()['duplicates'] == 2
    assert client.post('/api/imports', files={'file': ('fit.csv', statement([debit(amount="0.01")]))}).json()['inserted'] == 1
    report = client.get('/api/summary?month=2025-01').json()
    assert report['income_pence'] + report['outflow_pence'] == limit


def test_failure_during_write_rolls_back_and_allows_retry(settings, monkeypatch):
    import app.imports as imports
    real, calls = imports.classify, []

    def failing_second_row(row, available):
        calls.append(row)
        if len(calls) == 2:
            raise RuntimeError("synthetic write failure")
        return real(row, available)

    data = statement([debit(), debit()])
    monkeypatch.setattr(imports, "classify", failing_second_row)
    with pytest.raises(RuntimeError):
        import_statement(data, "partial.csv", settings)
    assert stored_counts(settings) == (0, 0)
    monkeypatch.setattr(imports, "classify", real)
    assert import_statement(data, "partial.csv", settings)["inserted"] == 2


def test_identity_is_exact_bytes_and_overlapping_exports_are_not_merged(settings):
    # Documented design (ARCHITECTURE.md): only byte-identical statements deduplicate.
    january = statement([debit("01/01/2025", "SYNTHETIC RENT"), debit("15/01/2025", "SYNTHETIC CAFE")])
    overlap = statement([debit("15/01/2025", "SYNTHETIC CAFE"), debit("01/02/2025", "SYNTHETIC RENT")])
    first = import_statement(january, "jan.csv", settings)
    second = import_statement(overlap, "jan-feb.csv", settings)
    assert first["sha256"] != second["sha256"] and second["inserted"] == 2
    resaved = b"\xef\xbb\xbf" + january.replace(b"\r\n", b"\n")
    assert import_statement(resaved, "jan-resaved.csv", settings)["inserted"] == 2
    with connect(settings.db_path) as db:
        assert db.execute("SELECT count(*) FROM transactions WHERE description='SYNTHETIC CAFE'").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM imports").fetchone()[0] == 3


def test_rules_walkthrough_matches_docs(client):
    walkthrough = (Path(__file__).parents[1] / "docs" / "RULES.md").read_text(encoding="utf-8")
    data = re.search(r"```csv\n(.*?)```", walkthrough, re.S).group(1).encode()
    assert client.post('/api/imports', files={'file': ('synthetic-rules.csv', data)}).json()['inserted'] == 9

    def categories():
        items = client.get('/api/transactions', params={'page_size': 100}).json()['items']
        return [row['category'] for row in sorted(items, key=lambda row: row['id'])]

    assert categories() == ['Utilities', 'Groceries', 'Utilities', 'Other', 'Unreviewed transfers',
                            'Groceries', 'Income', 'Other', 'Utilities']
    added = [client.post('/api/rules', json=rule).json() for rule in (
        {'pattern': 'LETTINGS', 'transaction_type': 'FPO', 'category': 'Housing', 'priority': 120},
        {'pattern': 'CAFE', 'category': 'Dining', 'priority': 150},
        {'pattern': 'CORNER', 'category': 'Shopping', 'priority': 150})]
    assert [(rule['id'], rule['reclassified']) for rule in added] == [(19, 9), (20, 9), (21, 9)]
    assert categories()[4] == 'Housing' and categories()[7] == 'Dining'
    assert client.patch('/api/transactions/6', json={'category': 'Household'}).json()['reason'] == 'Manual override'
    client.delete('/api/rules/20')
    assert categories()[5:8] == ['Household', 'Income', 'Shopping']
    client.patch('/api/transactions/6', json={'category': None})
    assert categories()[5] == 'Groceries'
    spending = {c['category']: c['amount_pence'] for c in client.get('/api/summary?month=2025-02').json()['categories']}
    assert spending == {'Housing': 65000, 'Other': 8000, 'Groceries': 3740, 'Utilities': 2000, 'Shopping': 450}
    recurring = client.get('/api/recurring').json()
    assert [(c['description'], c['cadence'], c['observations']) for c in recurring] == [('O2 MOBILE', 'monthly', 3)]


def test_browser_money_formatter_is_exact_at_integer_penny_bounds():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required to evaluate the browser money formatter")
    source = (Path(__file__).parents[1] / "app" / "static" / "app.js").read_text(encoding="utf-8")
    definition = re.search(r"^const money = .*$", source, re.M).group(0)
    script = definition + "\nprocess.stdout.write(JSON.stringify(JSON.parse(process.argv[1]).map(money)));"
    expected = {2**53 - 1: "£90,071,992,547,409.91", -(2**53 - 1): "-£90,071,992,547,409.91", 0: "£0.00",
                1: "£0.01", -1: "-£0.01", 100: "£1.00", 1234567: "£12,345.67", -2500: "-£25.00"}
    result = subprocess.run([node, "-e", script, json.dumps(list(expected))],
                            capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(result.stdout) == list(expected.values())
