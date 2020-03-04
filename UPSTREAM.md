# Upstream references and reuse

Reviewed: 2026-10-16. These projects are independent local portfolio work built with supervised Claude Code implementation and ChatGPT verification. The prefix year is a theme.

## Actual Budget

- Project: https://github.com/actualbudget/actual
- License inspected: https://raw.githubusercontent.com/actualbudget/actual/master/LICENSE.txt — MIT-style grant, copyright James Long, with preservation of copyright/permission notice required for copied substantial portions.
- Primary workflow references: https://actualbudget.org/docs/transactions/importing/ and https://actualbudget.org/docs/budgeting/rules/.
- Used as product/architecture references for explicit import handling, rules and original-payee preservation. No Actual Budget source code or assets have been copied or vendored at this point; no dependency on its service/database.
- Our chosen import behavior uses statement fingerprint plus row occurrence identities. Fuzzy same-amount/date/payee merging is unsuitable for this demo because distinct valid rows must survive. Rules are explicit deterministic priority with user override, rather than implying automatic behavioral learning.
- A reported upstream import issue (https://github.com/actualbudget/actual/issues/8464) is a useful lead for an independent regression scenario; it was closed as completed on October 12, 2026 via #9135. We have not reproduced it against Actual and do not claim a current independently verified upstream defect.

## Components

The runtime uses Python/FastAPI/SQLite and native browser standards. Exact installed versions and transitive dependencies will be recorded in the lockfile. Any future vendored code/assets must retain their original license/copyright and a pinned revision here. Dataset provenance and permissions are separately documented in DATA_SOURCES.md; software licenses do not license source data.

The implementation and documentation should identify actual adaptations and supervisor fixes. Do not remove required attribution, invent authorship/history, or present an upstream application as wholly original work.
