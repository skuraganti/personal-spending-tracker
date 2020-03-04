"""Bounded acquisition of the original author-linked historical MoneyVis snapshot.

No cookies, accounts or data-provided code. The cache is private/local and excluded.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request

SOURCE = "https://docs.google.com/spreadsheets/d/1pYTMqRhEI48hv_zNWZriHW_0vRSrA9ZSQ31aLT4Vbk0/export?format=csv"
PIN = "d74a8abaa3aae1f9b282f56b6b241f7c67ce1f89f0e80580a9ee23e5e58041f9"
FIELDS = ["Transaction Date", "Transaction Type", "Transaction Description", "Debit Amount", "Credit Amount", "Balance"]
ROOT = Path(__file__).resolve().parents[1]
LIMIT = 4_000_000

class AuthorRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != "https" or not (parsed.hostname == "docs.google.com" or (parsed.hostname or "").endswith(".googleusercontent.com")):
            raise ValueError("Unexpected source redirect; inspect before allowing it")
        return super().redirect_request(request, fp, code, message, headers, newurl)

def validate(data: bytes, *, allow_new: bool = False) -> dict:
    if len(data) > LIMIT:
        raise ValueError("Source exceeds 4 MB bound")
    digest = hashlib.sha256(data).hexdigest()
    if digest != PIN and not allow_new:
        raise ValueError("Snapshot changed; inspect provenance/schema before using --refresh")
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    if reader.fieldnames != FIELDS:
        raise ValueError("Unexpected statement schema")
    rows = list(reader)
    if not rows:
        raise ValueError("Empty source")
    return {"sha256": digest, "bytes": len(data), "records": len(rows), "columns": FIELDS}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Verify existing pinned bytes without network")
    parser.add_argument("--refresh", action="store_true", help="Explicitly accept a changed snapshot after source review; records new hash")
    args = parser.parse_args()
    target = ROOT / "data/raw/moneyvis.csv"
    if args.verify:
        print(json.dumps(validate(target.read_bytes()), indent=2))
        return
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), AuthorRedirects())
    request = urllib.request.Request(SOURCE, headers={"User-Agent": "PrivatePortfolioResearch/1.0"})
    with opener.open(request, timeout=30) as response:
        data = response.read(LIMIT + 1)
        content_type = response.headers.get("Content-Type", "")
    info = validate(data, allow_new=args.refresh)
    info.update(source_url=SOURCE, retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(), content_type=content_type,
                snapshot_kind="historical static snapshot, not live", publisher="MoneyVis authors, EuroVis 2023",
                license="Standalone data license unspecified; express local educational/research release; no redistribution claim")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".part")
    temporary.write_bytes(data)
    os.replace(temporary, target)
    (target.parent / "manifest.json").write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps(info, indent=2))

if __name__ == "__main__":
    main()
