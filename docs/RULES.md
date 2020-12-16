# Categorization rule walkthrough

This walkthrough uses the full local application and a small **synthetic** statement; the merchants, amounts and balances below are invented for illustration. Every category, reason and reclassification count shown here is the application's actual output for this file, and `tests/test_ledger.py::test_rules_walkthrough_matches_docs` re-runs it against this document.

**Use an empty, isolated demonstration ledger with the default rules.** The row and rule IDs below assume no earlier imports or rule edits. Do not run the numeric PATCH/DELETE examples against an existing personal ledger; inspect its actual transaction/rule IDs first and substitute them. Importing this fixture into an existing ledger changes the counts and IDs.

## How the full application classifies a row

For each transaction, `app/db.py` applies the first matching step:

1. **Manual override.** If the row has an override category, it wins. The reason is `Manual override`.
2. **Rules, in order of priority descending, then rule ID ascending.** A rule matches when:
   - its pattern, ignoring case, is **contained in** the stored description (an empty pattern matches every description), and
   - its optional transaction type, if set, **equals** the row's type exactly (types are stored upper-case).
   The first matching rule sets the category, and the reason records the rule ID, priority and pattern (or the type, for a type-only rule).
3. **Fallback.** Unmatched positive amounts become `Income` (`Credit; no matching rule`), and anything else becomes `Other` (`No matching rule; review this entry`).

Creating, editing or deleting a rule, and setting or clearing an override, reclassifies every stored transaction. New imports are classified with the rules in force at that moment. Rules match the description *as stored*, so a person-to-person transfer whose description was masked to `Person <hash>` at import no longer contains the original name.

## 1. Import the synthetic statement

Save this as `synthetic-rules.csv` and import it in the app (or `POST /api/imports`):

```csv
Transaction Date,Transaction Type,Transaction Description,Debit Amount,Credit Amount,Balance
04/01/2025,DD,O2 MOBILE,20.00,,980.00
03/02/2025,DEB,TESCO STORES 1234,12.40,,1967.60
04/02/2025,DD,O2 MOBILE,20.00,,1947.60
05/02/2025,DD,TESCO BANK LOAN,80.00,,1867.60
06/02/2025,FPO,ACME LETTINGS LTD,650.00,,1217.60
07/02/2025,DEB,AMAZON GROCERY,25.00,,1192.60
08/02/2025,BGC,SALARY ACME,,1000.00,2192.60
10/02/2025,DEB,CORNER CAFE,4.50,,2188.10
04/03/2025,DD,O2 MOBILE,20.00,,2168.10
```

With only the default rules, a fresh database gives:

| # | Type | Description | Category | Reason | Why |
|---|---|---|---|---|---|
| 1, 3, 9 | DD | O2 MOBILE | Utilities | Rule 14 · priority 90 · O2 | Pattern and type `DD` both match |
| 2 | DEB | TESCO STORES 1234 | Groceries | Rule 8 · priority 100 · TESCO | Rule 8 requires type `DEB` |
| 4 | DD | TESCO BANK LOAN | Other | No matching rule; review this entry | Same pattern, but type `DD` fails rule 8's type condition |
| 5 | FPO | ACME LETTINGS LTD | Unreviewed transfers | Rule 5 · priority 20 · FPO | Type-only rule; outbound amounts still count as spending |
| 6 | DEB | AMAZON GROCERY | Groceries | Rule 9 · priority 100 · GROCERY | Both `AMAZON` (90) and `GROCERY` (100) match; higher priority wins |
| 7 | BGC | SALARY ACME | Income | Credit; no matching rule | Credit fallback |
| 8 | DEB | CORNER CAFE | Other | No matching rule; review this entry | Debit fallback |

The reason text names the pattern only, even when the rule also has a type condition (rule 8 above).

## 2. Add rules and watch reclassification

Add three rules in this order with `POST /api/rules`. The **Category rules** interface supports description, category and priority; use the API for the optional type condition shown here:

| New ID | Priority | Pattern | Type | Category |
|---|---|---|---|---|
| 19 | 120 | `LETTINGS` | `FPO` | Housing |
| 20 | 150 | `CAFE` | | Dining |
| 21 | 150 | `CORNER` | | Shopping |

Each call reclassifies all 9 stored rows. Row 5 becomes **Housing** (`Rule 19 · priority 120 · LETTINGS`), because 120 outranks the default FPO rule at 20. Row 8 matches both rule 20 and rule 21 at the same priority, so the lower ID wins and it becomes **Dining** (`Rule 20 · priority 150 · CAFE`).

## 3. Override a row, then change the rules underneath it

- Override row 6 (AMAZON GROCERY) to `Household`. Its reason becomes `Manual override`.
- Delete rule 20. Row 8 falls through to rule 21 and becomes **Shopping**. Row 6 stays **Household**, because overrides are not affected by rule changes.
- Clear the override on row 6 (`PATCH /api/transactions/6` with `{"category": null}`). It returns to **Groceries** via rule 9.

The February summary then lists spending of Housing £650.00, Other £80.00, Groceries £37.40, Utilities £20.00 and Shopping £4.50. The £1,000.00 credit is income, not negative spending.

## 4. Recurring candidates are separate from categories

**Regular patterns** (`GET /api/recurring`) reports one candidate for this file: `O2 MOBILE`, monthly, £20.00, 3 observations (2025-01-04, 2025-02-04, 2025-03-04). Recurrence groups outflows by description and by amount (within 5%, minimum 1p, of the group's smallest amount). It then needs at least three distinct dates whose gaps mostly fit a weekly (7 ± 2 days), monthly (30 ± 4) or annual (365 ± 14) cadence. It skips Savings/Transfers categories and masked `Person …` labels, but is otherwise independent of the category a rule assigns. A candidate is a historical regularity, not a confirmed subscription.

## Pages demo rules are simpler

The browser demo on GitHub Pages ([docs/DEMO.md](DEMO.md)) has a one-shot **Apply rule** control, not this engine. It lower-cases the pattern, overwrites the category of every currently loaded row whose description contains it, and stops there:

- no priorities
- no transaction types
- no stored rules
- no overrides or reasons
- no reclassification of rows loaded later

**Reset** restores the synthetic fixture.
