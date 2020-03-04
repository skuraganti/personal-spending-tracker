"""One local ledger, with transactional statements and explicit classification."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

DEFAULT_RULES = [
    (1000, "SAVE THE CHANGE", "", "Savings"),
    (1000, "ESAVINGS", "", "Savings"),
    (1000, "TRADING212", "", "Savings"),
    (900, "", "TFR", "Savings"),
    (20, "", "FPO", "Unreviewed transfers"),
    (20, "", "FPI", "Unreviewed transfers"),
    (100, "LIDL", "", "Groceries"),
    (100, "TESCO", "DEB", "Groceries"),
    (100, "GROCERY", "", "Groceries"),
    (100, "SAINSBUR", "", "Groceries"),
    (90, "AMZN", "", "Shopping"),
    (90, "AMAZON", "", "Shopping"),
    (90, "VIRGIN MEDIA", "", "Utilities"),
    (90, "O2", "DD", "Utilities"),
    (90, "WATER", "", "Utilities"),
    (90, "ENERGY", "", "Utilities"),
    (90, "NON-GBP", "", "Fees"),
    (90, "", "FEE", "Fees"),
]


@contextmanager
def connect(path):
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS imports(
          id TEXT PRIMARY KEY,name TEXT NOT NULL,rows INTEGER NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS rules(
          id INTEGER PRIMARY KEY,priority INTEGER NOT NULL,pattern TEXT NOT NULL,
          transaction_type TEXT NOT NULL DEFAULT '',category TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS transactions(
          id INTEGER PRIMARY KEY,import_id TEXT NOT NULL REFERENCES imports(id),
          row_number INTEGER NOT NULL,date TEXT NOT NULL,transaction_type TEXT NOT NULL,
          description TEXT NOT NULL,amount_pence INTEGER NOT NULL,balance_pence INTEGER,
          category TEXT NOT NULL,reason TEXT NOT NULL,rule_id INTEGER,
          override_category TEXT,UNIQUE(import_id,row_number));
        CREATE INDEX IF NOT EXISTS tx_date ON transactions(date);
        CREATE INDEX IF NOT EXISTS tx_category ON transactions(category,date);
        CREATE TABLE IF NOT EXISTS budgets(
          id INTEGER PRIMARY KEY,month TEXT NOT NULL,category TEXT NOT NULL,
          limit_pence INTEGER NOT NULL CHECK(limit_pence>=0),
          threshold_percent INTEGER NOT NULL CHECK(threshold_percent BETWEEN 1 AND 100),
          UNIQUE(month,category));
        """)
        version = db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
        if not version:
            db.executemany("INSERT INTO rules(priority,pattern,transaction_type,category) VALUES(?,?,?,?)", DEFAULT_RULES)
            db.execute("INSERT INTO metadata VALUES('schema','2')")
        elif version[0] == '1':
            # Only replace untouched original defaults; user-edited rules stay intact.
            changed = db.execute("""UPDATE rules SET category='Unreviewed transfers',priority=20
                                  WHERE id IN (5,6) AND pattern='' AND transaction_type IN ('FPO','FPI')
                                  AND category='Transfers' AND priority=800""").rowcount
            if changed:
                reclassify(db)
            db.execute("UPDATE metadata SET value='2' WHERE key='schema'")


def rules(db):
    return [dict(r) for r in db.execute("SELECT * FROM rules ORDER BY priority DESC,id ASC")]


def classify(row, available):
    if row.get("override_category"):
        return row["override_category"], "Manual override", None
    for rule in available:
        if rule["transaction_type"] and rule["transaction_type"] != row["transaction_type"]:
            continue
        if rule["pattern"].upper() not in row["description"].upper():
            continue
        return rule["category"], f"Rule {rule['id']} · priority {rule['priority']} · {rule['pattern'] or rule['transaction_type']}", rule["id"]
    if row["amount_pence"] > 0:
        return "Income", "Credit; no matching rule", None
    return "Other", "No matching rule; review this entry", None


def reclassify(db):
    available = rules(db)
    updates = []
    for row in db.execute("SELECT * FROM transactions"):
        category, reason, rule_id = classify(dict(row), available)
        updates.append((category, reason, rule_id, row["id"]))
    db.executemany("UPDATE transactions SET category=?,reason=?,rule_id=? WHERE id=?", updates)
    return len(updates)
