# Data sources (initial reviewed selection)

Retrieval date: 2026-10-16 UTC. Actual research/development date.

| Candidate | Original publisher / source | Authenticity and access | License / use | Decision |
|---|---|---|---|---|
| MoneyVis / MoneyData | Firat, Vytla, Singh, Jiang, Laramee; EuroVis 2023, DOI [10.2312/evs.20231052](https://doi.org/10.2312/evs.20231052); [original paper](https://people.cs.nott.ac.uk/blaramee/research/financeVis/firat23moneyVis.pdf), [author-linked sheet](https://docs.google.com/spreadsheets/d/1pYTMqRhEI48hv_zNWZriHW_0vRSrA9ZSQ31aLT4Vbk0/edit) | Authors describe an anonymized real retail account; anonymous CSV export verified | Expressly released for research/analysis. Article is CC BY; no separate machine-readable data license confirmed. Do not claim article license applies to dataset; local educational/research use only and no data redistribution | Selected: matches statement workflow and observed bill history |
| Online Retail | [UCI / Daqing Chen](https://archive.ics.uci.edu/dataset/352/online+retail) | Real UK sales invoices; original repository | CC BY 4.0 stated by UCI | Rejected: retailer sales are not household bank spending |
| PKDD99 Financial | [Original Discovery Challenge](https://sorry.vse.cz/~berka/challenge/pkdd1999/berka.htm); [CTU repository](https://relational.fel.cvut.cz/) | Historical relational data; secondary descriptions disagree about artificial vs real/anonymized origins | Standalone license not established in this review | Rejected: larger and weaker current provenance/access confidence |

## Selected snapshot

- CSV endpoint: https://docs.google.com/spreadsheets/d/1pYTMqRhEI48hv_zNWZriHW_0vRSrA9ZSQ31aLT4Vbk0/export?format=csv
- Snapshot: 301,864 bytes; 6,567 rows plus header.
- SHA-256: `d74a8abaa3aae1f9b282f56b6b241f7c67ce1f89f0e80580a9ee23e5e58041f9`.
- Header: Transaction Date, Transaction Type, Transaction Description, Debit Amount, Credit Amount, Balance.
- GBP is an assumption from UK-source context, not a raw currency field; dates DD/MM/YYYY and monetary values decimal strings. Some transaction types are blank; do not silently drop these rows.
- Dates: historical 2015–2022; not live. Source single-account selection and anonymization distort representativeness; no claim about population spending or confirmed obligations. Description fields may still contain counterparty names. Do not reidentify or link.
- All raw data stay under excluded `data/`; scripts must record retrieval timestamp, byte count and SHA256, fail on unexpected schema/size/hash unless an explicit refresh is requested.
- Preparation records exact cleaning/masking, duplicate strategy, schema and counts in the manifest; SOURCE_MANIFEST.json consolidates the original cache metadata without changing its retrieval/preparation timestamps. No model training split applies; small synthetic edge-case fixtures must be labeled.

## Independent source review

2026-10-16: research-source-reviewer checked the original paper, UCI page, attempted the original PKDD and sheet reads, and independently matched the local snapshot hash/counts. Prefer wording “author-described anonymized historical bank transactions”; no independent authenticity audit performed. There are no category/recurrence labels or currency field in the CSV. GBP is a documented assumption from UK-source context, not a verified per-row attribute. Weekend posting shifts and missing timestamps limit cadence inference. PKDD authenticity/license unresolved, not verified artificial. Data licensing is unspecified separately from the article.

## Acquisition and preparation actually executed

`python3 scripts/acquire_data.py --verify` independently rechecked the pinned raw bytes without network. The acquisition script supports anonymous, bounded HTTPS GET only from the author sheet and its Google export redirects, no cookies/proxies/accounts, a 4 MB bound, explicit schema, pinned default checksum and atomic replacement. A changed snapshot requires deliberate `--refresh` and a new provenance review.

`python3 scripts/prepare_data.py` preserved all 6,567 rows/order/dates/types/money fields, masked descriptions in FPI/FPO/PAY/BGC/DEP/CHQ, and produced 309,155 bytes with SHA-256 `259b973e66c489b8c7aef9f3f80138d581105aa60ca7653afe87411a3a860e5d`. Exactly 668 descriptions changed. The importer additionally applies the worker's documented person-shaped-name heuristic; this can over-mask organisations and miss unusual names. Masking is a privacy convenience, not an anonymity guarantee; avoid reidentification and redistribution. All cache/database paths are excluded.

Demo imports **only the prepared version**. Statement identity is byte SHA-256 and each row retains its occurrence index: identical valid rows survive and exact repeated imports add zero. Different byte versions or overlapping exports remain separate statements and require human review; do not import both raw and prepared versions into one demo ledger. No fuzzy merging is performed.

Amounts become signed integer pennies, dates ISO dates, optional balances integer pennies. Exactly one debit/credit column must be present; invalid files reject atomically with bounded row diagnostics. Blank types remain visible. User-defined rules and budgets are local configuration, not publisher annotations. Default outbound FPO transfer mechanics do not establish self-transfer ownership: they remain “Unreviewed transfers” and count as spending until reviewed. Recurrence is an amount-cluster/date-gap heuristic (5% with minimum one penny; weekly ±2 days, monthly ±4, annual ±14; >=3 distinct dates; >=75% matching gaps), not ground truth.

No training/test split applies to this non-AI project. Synthetic validation fixtures in tests are distinct from the observed source rows. Real HTTP verification checked 6,567 records, debit total 51,117,892 pennies, credit total 50,320,329 pennies and July 2022's 79 rows against an independently computed raw-CSV baseline.
