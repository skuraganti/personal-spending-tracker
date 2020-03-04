"""Validate complete statements before starting a database write."""
import csv
import datetime as dt
import hashlib
import io
from pathlib import Path

from .db import classify, connect, rules
from .masking import mask_description
from .money import parse_optional_pennies, parse_pennies

FIELDS = ["Transaction Date", "Transaction Type", "Transaction Description", "Debit Amount", "Credit Amount", "Balance"]


class ImportFailure(ValueError):
    def __init__(self, diagnostics):
        super().__init__("Statement rejected; no rows were written")
        self.diagnostics = diagnostics


def parse_statement(data, settings):
    if not data or len(data) > settings.max_import_bytes:
        raise ImportFailure([{"row": 0, "error": "Empty file or import byte limit exceeded"}])
    parsed, diagnostics, blank_types = [], [], 0
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")), strict=True)
        if reader.fieldnames != FIELDS:
            raise ImportFailure([{"row": 1, "error": "Expected the six documented MoneyVis CSV columns in order"}])
        for number, row in enumerate(reader, 2):
            if number - 1 > settings.max_import_rows:
                raise ImportFailure([{"row": number, "error": "Import row limit exceeded"}])
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("Incorrect column count")
                if any(len(value) > 3000 or "\x00" in value for value in row.values()):
                    raise ValueError("Field too long or contains a null character")
                date = dt.datetime.strptime(row[FIELDS[0]].strip(), "%d/%m/%Y").date()
                debit = parse_optional_pennies(row[FIELDS[3]])
                credit = parse_optional_pennies(row[FIELDS[4]])
                if (debit is not None) == (credit is not None):
                    raise ValueError("Exactly one of debit and credit must be populated")
                amount = -debit if debit is not None else credit
                kind = row[FIELDS[1]].strip().upper()
                if len(kind) > 20:
                    raise ValueError("Transaction type too long")
                description = mask_description(row[FIELDS[2]].strip(), kind)
                if not description:
                    raise ValueError("Description is required")
                balance_text = row[FIELDS[5]].strip()
                balance = None
                if balance_text:
                    balance = parse_pennies(balance_text.removeprefix("-")) * (-1 if balance_text.startswith("-") else 1)
                blank_types += int(not kind)
                parsed.append({"row_number": number - 1, "date": date.isoformat(), "transaction_type": kind,
                               "description": description, "amount_pence": amount, "balance_pence": balance})
            except ValueError as error:
                if len(diagnostics) < settings.max_diagnostics:
                    diagnostics.append({"row": number, "error": str(error)})
    except (UnicodeError, csv.Error) as error:
        raise ImportFailure([{"row": 0, "error": f"Invalid CSV encoding or structure: {type(error).__name__}"}]) from error
    if diagnostics:
        raise ImportFailure(diagnostics)
    if not parsed:
        raise ImportFailure([{"row": 0, "error": "No transaction records"}])
    return parsed, blank_types


def import_statement(data, filename, settings):
    parsed, blank_types = parse_statement(data, settings)
    digest = hashlib.sha256(data).hexdigest()
    with connect(settings.db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT * FROM imports WHERE id=?", (digest,)).fetchone()
        if existing:
            return {"sha256": digest, "inserted": 0, "duplicates": existing["rows"], "rows": existing["rows"], "blank_types": blank_types}
        db.execute("INSERT INTO imports VALUES(?,?,?,?)", (digest, Path(filename).name[:200], len(parsed), dt.datetime.now(dt.timezone.utc).isoformat()))
        available = rules(db)
        for row in parsed:
            category, reason, rule_id = classify(row, available)
            db.execute("""INSERT INTO transactions(import_id,row_number,date,transaction_type,description,amount_pence,
                       balance_pence,category,reason,rule_id) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                       (digest, row["row_number"], row["date"], row["transaction_type"], row["description"], row["amount_pence"],
                        row["balance_pence"], category, reason, rule_id))
    return {"sha256": digest, "inserted": len(parsed), "duplicates": 0, "rows": len(parsed), "blank_types": blank_types}
