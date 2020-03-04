"""Prepare an explicitly documented privacy-reduced demo, never generated transactions."""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import io
import json
from acquire_data import FIELDS, ROOT, validate

# These transaction kinds can contain person-to-person or salary/deposit counterparties.
# Masking deliberately sacrifices merchant detail for these kinds. It is not an anonymity guarantee.
MASK_TYPES = {"FPI", "FPO", "PAY", "BGC", "DEP", "CHQ"}

def main() -> None:
    raw = (ROOT / "data/raw/moneyvis.csv").read_bytes()
    source = validate(raw)
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    masked = 0
    for row in rows:
        kind = row["Transaction Type"].strip().upper()
        if kind in MASK_TYPES:
            row["Transaction Description"] = "Published counterparty hidden (" + kind + ")"
            masked += 1
    folder = ROOT / "data/prepared"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "moneyvis-demo.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    data = target.read_bytes()
    manifest = {"prepared_at": dt.datetime.now(dt.timezone.utc).isoformat(), "source_sha256": source["sha256"],
                "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "records": len(rows), "masked_rows": masked,
                "transform": "Preserve every row, order, date, type and money string. Replace description for FPI/FPO/PAY/BGC/DEP/CHQ with a type-specific hidden-counterparty label. No sampling, imputation, categorization or synthetic rows.",
                "currency": "GBP assumed from original UK source context; absent from raw schema",
                "splits": "No model fitting. Synthetic domain test fixtures are separate from observed demo data.",
                "limitations": "Masking reduces detail and may merge counterparties for analysis; transfer-like kinds must not become recurrence evidence merely because masked text matches. Raw source remains excluded/local. Not a guarantee of anonymity."}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()
