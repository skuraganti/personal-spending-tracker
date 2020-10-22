# Ledger browser demonstration

Open this directory through the repository Pages URL or a local static HTTP server so `fetch(./demo-data.json)` works. The full Python/Docker application remains in the source repository.

The bundled fixture is explicitly synthetic GBP data; no MoneyVis data is redistributed. Month/category filters, category rules, monthly budget alert, spending bars, recurring-charge heuristic, transaction table, reset and bounded local CSV preview execute entirely in the browser. CSV import is limited to 1 MiB and 5,000 rows, validates the complete file before replacement, and never uploads data. Spending and recurring-charge indications are simple heuristics, not financial advice.

Source context: [MoneyVis paper](https://doi.org/10.2312/evs.20231052). [Full Python/Docker source and local startup](https://github.com/skuraganti/personal-spending-tracker).
