# Release status

**Local release gates: verified on 2026-10-16.** Source, native tests, Docker workflow/persistence, Pages browser/mobile/error states and publication privacy review passed. Actual publication is recorded by GitHub commit/deployment metadata after this prepared initial commit. See [VERIFICATION.md](VERIFICATION.md) for exact checks and limits.

Local: `sh scripts/stack.sh up` → http://127.0.0.1:8280. [Pages demo](https://skuraganti.github.io/personal-spending-tracker/) · [Source](https://github.com/skuraganti/personal-spending-tracker). Pages uses static browser interactions; full Python services run locally. Runtime databases, caches, model-control files and credentials stay excluded. The browser fixture is entirely synthetic. Author-described anonymized MoneyVis data are not redistributed because their standalone license is unresolved. GBP is a documented assumption for that local research dataset. Recurrences are candidates, not ground truth.

Next maintenance action: use the documented setup, verify original-source checksums before updating fixtures, rerun affected tests and retain failed/uncertain evaluation outcomes. No hosted inference or unattended service is supplied by Pages.
