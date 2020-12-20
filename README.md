# Ledger — personal spending tracker

**[Open the GitHub Pages browser demo](https://skuraganti.github.io/personal-spending-tracker/)** · [Architecture](ARCHITECTURE.md) · [Data sources](DATA_SOURCES.md) · [Verification](VERIFICATION.md)

Import real CSV transactions, apply category rules and review possible recurring payments. Ledger summarizes spending and raises local budget alerts you can configure. It has no bank connections.

## Two ways to explore

Try the **Pages site** with an entirely synthetic example. It runs in the browser using relative assets, with no backend, credentials or model calls. Its rule control reclassifies transactions with a one-shot "contains" rule ([docs/DEMO.md](docs/DEMO.md)). Run the **full Python/Docker application** for stored priority rules, transaction-type conditions, manual overrides and reclassification ([docs/RULES.md](docs/RULES.md)). Pages cannot run the backend.

## Run the full application locally

Requirements: a POSIX host (macOS or Linux), Python3.13+, [uv](https://docs.astral.sh/uv/), Docker and Docker Compose. No GPU is required. Run one portfolio stack at a time on a small machine.

```sh
uv sync --frozen
uv run python scripts/bootstrap.py
sh scripts/stack.sh up
```

Open **http://127.0.0.1:8280**. To stop the app, use `sh scripts/stack.sh stop`; this keeps the repository's own named volume. The helpers use the current Docker context or an explicit `DOCKER_HOST`, without choosing a personal machine profile. Images, networks and volumes use unique `portfolio-release-*` names, separate from the original development stacks. Host ports bind to 127.0.0.1.

To restart without losing data, run `sh scripts/stack.sh stop` and then `sh scripts/stack.sh up`.

### Import format

A statement is a UTF-8 CSV (an optional BOM is fine) whose header is exactly `Transaction Date,Transaction Type,Transaction Description,Debit Amount,Credit Amount,Balance`.

- **Dates** are `DD/MM/YYYY`.
- **Amounts** use ASCII digits with at most two decimal places, and each row fills exactly one of debit or credit. **Balance** may be signed.
- **Line endings:** CRLF, LF or bare CR. Quoted fields may contain commas and newlines, and blank lines are skipped.
- **Limits:** 1,000,000 bytes and 50,000 rows by default (`.env.example`).
- **Numeric safety bound:** every amount or balance must be at most 2^53 − 1 pennies (about £90 trillion). A statement is also rejected if it would push the gross ledger, the sum of absolute values of all stored amounts, past that bound. Totals then stay exact in SQLite and JavaScript. This guards integer overflow, not plausibility; ledgers stored before the bound existed are not rewritten.
- **Atomic:** Ledger validates the whole file before writing anything. One bad row rejects the file.
- **Identity:** Ledger recognizes a byte-identical file as already imported. Any other file starts a new statement, including a re-saved or overlapping export. Identical rows remain separate occurrences.

For your own bank-export CSV, use this schema. Optional local research acquisition of the author-linked MoneyVis dataset uses `uv run python scripts/acquire_data.py` followed by `uv run python scripts/prepare_data.py`. Review DATA_SOURCES.md first; files remain excluded from Git. No transaction data or actual-account screenshots are included in this public repository. The Pages fixture is not presented as observed financial data.

## Verify

```sh
uv run pytest
uv run ruff check .
python3 -m http.server 8008 --bind 127.0.0.1 --directory docs
```

The final command previews Pages at http://127.0.0.1:8008. For Ledger, bootstrap only creates the local `data/verification/` directory; it downloads nothing. Native tests use synthetic statements, including the [rule walkthrough](docs/RULES.md). Install Node.js to run the exact browser-currency formatter regression; that single test is skipped when Node is unavailable. Unit fixtures, actual-source checks, captured evaluations and browser simulations are distinguished in [VERIFICATION.md](VERIFICATION.md). No model call is required for the native test suite.

## Scope and limitations

The browser fixture is entirely synthetic. Author-described anonymized MoneyVis data are not redistributed because their standalone license is unresolved. GBP is a documented assumption for that local research dataset. Recurrences are candidates, not ground truth.

[DEMO.md](DEMO.md) describes a local walkthrough, [docs/RULES.md](docs/RULES.md) a reproducible categorization walkthrough and [docs/DEMO.md](docs/DEMO.md) the Pages interactions. [DECISIONS.md](DECISIONS.md), [PLAN.md](PLAN.md) and [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) record engineering choices and source versions. Upstream components and original data publishers are credited in [UPSTREAM.md](UPSTREAM.md); third-party licenses remain in force. Original application code and authored documentation remain unlicensed; see [LICENSING.md](LICENSING.md) for reserved rights and third-party boundaries.

## Explore projects

[Ledger](https://skuraganti.github.io/personal-spending-tracker/) · [Fieldglass](https://skuraganti.github.io/live-earth-dashboard/) · [Relay](https://skuraganti.github.io/data-pipeline-monitor/) · [Folio](https://skuraganti.github.io/private-ai-knowledge-engine/) · [Contour](https://skuraganti.github.io/ai-codebase-explorer/) · [TraceLab](https://skuraganti.github.io/ai-agent-evaluation-lab/) · [Faultline](https://skuraganti.github.io/ai-incident-investigator/)

Defaults work without copying `.env.example`. Dependency installation needs internet access. Ledger has no model integration or host bridge.

## Implementation history

- CSV statement imports with validation and duplicate detection.
- Deterministic category rules, recurring-payment candidates and configurable budget alerts.
- A local spending dashboard and a separate browser-only demonstration using a synthetic fixture.
