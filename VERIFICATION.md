# Release verification — 2026-10-16

Actual development and release preparation 2026-10-16. This report records checks on the sanitized public source copy before its initial commit. Deployment is checked separately after pushing, without backdated commits. Passing these bounded checks does not guarantee every future feed, model response or workload.

| Check | Observed result |
|---|---|
| Clean source environment | `uv sync --frozen`, project-specific `scripts/bootstrap.py`: passed |
| Native suite | **19 passed** with Python 3.14.8; FastAPI/Starlette emitted a TestClient deprecation warning |
| Lint | `uv run ruff check .`: passed; pinned upstream corpus files excluded from project style rules |
| Docker | Digest-pinned Python 3.13 image built; startup, HTTP health and application page passed |
| Workflow | 32 synthetic rows imported; identical import deduplicated |
| Persistence | Restarted app container; workflow state retained |
| Browser | Isolated Chromium via agent-browser 0.38.1; 10 domain assertions passed; native input/click controls passed |
| Error state | Fixture temporarily unavailable: visible recoverable error; restored fixture loads after reload |
| Responsive layout | 1440×1000 and 390×844 inspected; 390px document width with no page overflow |
| Accessibility | axe-core 4.12.1, WCAG 2 A/AA and 2.1 AA tags: **0 detected violations** |
| Privacy | Candidate-file Gitleaks scan passed; no private home paths, unrelated service IDs, credentials or mutable data included |
| Release inference | **0 model calls**; recorded original model studies remain distinct from release checks |

Browser scenarios: 32 synthetic transactions render; month filter; budget overage exact; category total; local categorization; fixture reset preserves valid filter; impossible calendar date atomically rejected; valid CSV processed locally; reset defeats delayed CSV read; overflow budget rejected.

Some axe color checks on clipped scroll contents require manual review. Visible desktop/mobile views and the authored foreground/background palette were inspected; the minimum checked ink/muted/link ratio against the declared page/panel backgrounds was 5.31:1. This is a bounded audit, not a universal accessibility certification. Scroll regions are keyboard focusable and tables accompany charts/graphs.

## Corrections and retesting

Impossible calendar dates are rejected atomically; upload epochs prevent delayed CSV reads from replacing a reset or newer import. Budgets reject overflow and honor the displayed maximum. Chart groups and scrollable tables gained appropriate keyboard access.

## Recorded findings and limitations

The browser fixture is entirely synthetic. Author-described anonymized MoneyVis data are not redistributed because their standalone license is unresolved. GBP is a documented assumption for that local research dataset. Recurrences are candidates, not ground truth.

Native tests use explicit fixtures, original-source boundary checks and simulated model responses; they do not perform live inference. See [PUBLIC_DEMO_DATA.md](PUBLIC_DEMO_DATA.md) for the curated Pages fixture and checksum, [DATA_SOURCES.md](DATA_SOURCES.md) for publisher/version/rights and [UPSTREAM.md](UPSTREAM.md) for attribution. Original model studies have small samples and cannot establish general performance or costs.

## Reproduce

```sh
uv sync --frozen
uv run python scripts/bootstrap.py
uv run pytest
uv run ruff check .
sh scripts/stack.sh up
```

Local URL: http://127.0.0.1:8280. The container limit is 256 MiB for the app, plus Docker and host process overhead. Tested one portfolio stack at a time on an ARM Mac with 8 GiB host RAM and a 2 GiB Docker VM. No GPU. Defaults use independent named volumes and localhost bindings. Stack stop retains state; no unrelated services are managed.

For Pages: `python3 -m http.server 8008 --bind 127.0.0.1 --directory docs`. With optional agent-browser 0.38.1 installed, run `sh scripts/check-pages.sh`; assertions are in `tests/pages-smoke.js`. No browser automation package is shipped to Pages.

## Import and rule maintenance verification

- Native suite: **51 passed** with Python 3.14.8 and Node available; Ruff passed. The existing TestClient deprecation warning remains.
- Regression coverage includes BOM/CRLF/bare-CR and quoted CSV, malformed/oversized inputs, ASCII monetary fields, atomic rejection, occurrence identity, rule priority/ties and overrides, and exact currency display at both signed integer-penny limits.
- Docker image rebuilt; isolated localhost HTTP checks passed for import/reimport, rule tie ordering, override lifecycle, atomic amount rejection, summary totals and budget alerts. Restart preserved the records, saved rule and budget.
- The 6,567-row prepared MoneyVis research snapshot passed in a separate temporary native database; a repeated import added zero rows. Source bytes were not redistributed.
- Chrome verified a file-chooser import reporting **0 inserted / 2 already imported**, plus exact large-amount rendering at **£90,071,992,547,389.71** using synthetic input.
- The rule walkthrough runs against its own synthetic CSV and an empty isolated database. GitHub Pages remains the simpler synthetic browser demonstration.

The gross-ledger guard scans existing amounts for each new statement. Existing databases already beyond the numeric bound are not automatically repaired; their summaries may still overflow, and new nonduplicate imports are rejected. The guard is a numeric safety limit, not a plausibility check. These checks do not establish correctness for every possible workload.
