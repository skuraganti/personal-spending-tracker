"""Synthetic edge fixtures only; real snapshot checks are separate acceptance evidence."""
import csv
import io
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.config import Settings, get_settings
from app.db import connect, initialize
from app.imports import FIELDS, ImportFailure, import_statement
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
