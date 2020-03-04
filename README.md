# Ledger — personal spending tracker

**[Open the GitHub Pages browser demo](https://skuraganti.github.io/2020-personal-spending-tracker/)** · [Architecture](ARCHITECTURE.md) · [Data sources](DATA_SOURCES.md) · [Verification](VERIFICATION.md)

Real CSV transaction imports, rule-based categorization, recurrence candidates, spending summaries and configurable local budget alerts. No bank connections.

**Theme year: 2020. Actual development: 2026-10-16.** The2020–2026portfolio timeline describes technology themes and increasing sophistication, not historical completion dates. Commits and publication use their actual dates. See [project.json](project.json).

## Two ways to explore

The **Pages site** is a self-contained browser demonstration with relative assets and no backend, credentials or model calls. Its data modes are visibly labeled: original public-publisher snapshots/recorded observations where allowed, explicit simulation where appropriate, and an entirely synthetic Ledger fixture. The repository also contains the **full Python/Docker application**; Pages cannot execute its backend or background workers.

## Run the full application locally

Requirements: Python3.13+, [uv](https://docs.astral.sh/uv/), Docker and Docker Compose. Contour also needs Node24+ for the trusted official TypeScript parser when running native tests; its Docker image includes Node. No GPU is required. Run one portfolio stack at a time on a small machine.

```sh
uv sync --frozen
uv run python scripts/bootstrap.py
sh scripts/stack.sh up
```

Open **http://127.0.0.1:8280**. Stop with `sh scripts/stack.sh stop`; this retains this repository's independent named volume. Helpers honor your current Docker context or explicitly supplied `DOCKER_HOST`; they do not select a personal machine profile. Images/networks/volumes are uniquely named `portfolio-release-*`, keeping the original development stacks separate. Host ports bind to127.0.0.1.

For your own bank-export CSV, use the documented import schema. Optional local research acquisition of the author-linked MoneyVis dataset uses `uv run python scripts/acquire_data.py` followed by `uv run python scripts/prepare_data.py`. Review DATA_SOURCES.md first; files remain excluded from Git. No transaction data or actual-account screenshots are included in this public repository. The Pages fixture is not presented as observed financial data.

## Verify

```sh
uv run pytest
uv run ruff check .
python3 -m http.server 8008 --bind 127.0.0.1 --directory docs
```

The final command previews Pages at http://127.0.0.1:8008. Bootstrap prepares this checkout's own data before data-boundary integration tests. Unit fixtures, actual-source checks, captured evaluations and browser simulations are distinguished in [VERIFICATION.md](VERIFICATION.md). No model call is required for the native test suite.

## Scope and limitations

The browser fixture is entirely synthetic. Author-described anonymized MoneyVis data are not redistributed because their standalone license is unresolved. GBP is a documented assumption for that local research dataset. Recurrences are candidates, not ground truth.

[DEMO.md](DEMO.md) describes a local walkthrough; [docs/DEMO.md](docs/DEMO.md) describes the Pages interactions. [DECISIONS.md](DECISIONS.md), [PLAN.md](PLAN.md) and [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) record engineering choices and source versions. All original implementation was developed with Claude Code through the approved connection and ChatGPT architecture, integration, review, correction and independent verification. Upstream components and original data publishers are credited in [UPSTREAM.md](UPSTREAM.md); third-party licenses remain in force. No additional license grant for the original implementation has been selected.

## Portfolio themes

[2020](https://skuraganti.github.io/2020-personal-spending-tracker/) · [2021](https://skuraganti.github.io/2021-live-earth-dashboard/) · [2022](https://skuraganti.github.io/2022-data-pipeline-monitor/) · [2023](https://skuraganti.github.io/2023-private-ai-knowledge-engine/) · [2024](https://skuraganti.github.io/2024-ai-codebase-explorer/) · [2025](https://skuraganti.github.io/2025-ai-agent-evaluation-lab/) · [2026](https://skuraganti.github.io/2026-ai-incident-investigator/)

Prerequisites: a POSIX host (macOS or Linux), Docker with Compose, and `uv`. Native scripts use POSIX process/file-lock facilities. Dependency installation needs internet; Relay, Folio and TraceLab also download original-source data during bootstrap. Defaults work without copying `.env.example`. Optional model integration uses a locally configured host bridge; inference may be remote. The supplied bridge requires `zsh`, an existing `claude-omni` command and the approved `cookllm` route; no provider is included or enabled by Pages.
