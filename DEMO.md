# A five-minute real-data demonstration

1. Start `sh scripts/stack.sh up` and open http://127.0.0.1:8280. Source dates and assumed GBP are visible.
2. Import `data/prepared/moneyvis-demo.csv`: 6,567 observed transactions, including 61 blank-type credits. Import it again: zero inserted, 6,567 already imported. Inspect its source fingerprint in import history.
3. Choose July 2022: 79 records, £1,150.96 recorded credits and £3,652.90 debits. Spending and savings/explicit-transfer totals are separate; unreviewed outbound bank transfers still count as spending.
4. Click Groceries, inspect rule explanations, page/search the ledger and temporarily override a category. Return to rules; create a specific higher-priority rule, inspect reclassification and remove it. Manual overrides remain explicit. [docs/RULES.md](docs/RULES.md) walks through the same precedence, type-condition, tie-break and override behaviour on a small synthetic statement that needs no research data.
5. Open Regular patterns. Examine O2/Virgin Media candidates, supporting dates, amount tolerance and uncertainty. These observations end in 2022 and do not confirm any present subscription.
6. Set a July 2022 Groceries limit to £10 and threshold 80%. The actual £158.74 grocery debits trigger a local over-budget alert. The budget itself is demonstration configuration, not observed publisher data.
7. Run `sh scripts/stack.sh stop`, then `sh scripts/stack.sh up`. The 6,567 records and budgets remain in this project's named volume. Stop this stack when moving to another portfolio project; the volume is kept.

The invalid import, duplicate-row, security, recurrence false-positive and synthetic refresh-failure cases are reproducible through the documented verification scripts/tests. No bank account, email alert or public service is involved.
