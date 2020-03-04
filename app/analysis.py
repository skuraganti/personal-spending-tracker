"""Deterministic historical analysis. Regularity is evidence, not an obligation."""
from collections import defaultdict
import datetime as dt
from statistics import median

TRANSFER_CATEGORIES = {"Savings", "Transfers"}


def summary(db, month):
    rows = [dict(r) for r in db.execute("SELECT * FROM transactions WHERE substr(date,1,7)=?", (month,))]
    categories = defaultdict(int)
    for row in rows:
        if row["amount_pence"] < 0 and row["category"] not in TRANSFER_CATEGORIES:
            categories[row["category"]] -= row["amount_pence"]
    trends = [dict(r) for r in db.execute("""SELECT substr(date,1,7) month,
              sum(CASE WHEN amount_pence>0 THEN amount_pence ELSE 0 END) income_pence,
              sum(CASE WHEN amount_pence<0 THEN -amount_pence ELSE 0 END) outflow_pence
              FROM transactions GROUP BY month ORDER BY month""")]
    return {"month": month, "currency": "GBP", "currency_assumption": True, "rows": len(rows),
            "income_pence": sum(r["amount_pence"] for r in rows if r["amount_pence"] > 0),
            "outflow_pence": -sum(r["amount_pence"] for r in rows if r["amount_pence"] < 0),
            "spending_pence": sum(categories.values()),
            "transfers_pence": -sum(r["amount_pence"] for r in rows if r["amount_pence"] < 0 and r["category"] in TRANSFER_CATEGORIES),
            "categories": [{"category": k, "amount_pence": v} for k, v in sorted(categories.items(), key=lambda x: (-x[1], x[0]))],
            "trends": trends}


def budget_status(db, month):
    result = []
    for row in db.execute("SELECT * FROM budgets WHERE month=? ORDER BY category", (month,)):
        budget = dict(row)
        spent = db.execute("SELECT coalesce(-sum(amount_pence),0) FROM transactions WHERE substr(date,1,7)=? AND category=? AND amount_pence<0", (month, row["category"])).fetchone()[0]
        limit = row["limit_pence"]
        alert = spent * 100 >= limit * row["threshold_percent"] if limit else spent > 0
        state = "over" if spent > limit else "warning" if alert else "ok"
        budget.update(spent_pence=spent, remaining_pence=limit-spent, alert=alert, state=state,
                      used_percent=round(spent * 100 / limit, 1) if limit else None)
        result.append(budget)
    return result


def recurring(db):
    merchants = defaultdict(list)
    for row in db.execute("SELECT * FROM transactions WHERE amount_pence<0 ORDER BY date,id"):
        if row["category"] in TRANSFER_CATEGORIES or row["description"].startswith(("Person ", "Published counterparty hidden")):
            continue
        merchants[row["description"].upper()].append(dict(row))
    candidates = []
    for merchant, rows in merchants.items():
        clusters = []
        for row in sorted(rows, key=lambda r: (-r["amount_pence"], r["date"])):
            amount = -row["amount_pence"]
            # Amounts are sorted; a fixed lower anchor bounds the entire cluster.
            # Avoid recomputing medians or scanning every cluster for each record.
            group = clusters[-1] if clusters else None
            anchor = -group[0]["amount_pence"] if group else 0
            if group is None or amount-anchor > max(1, anchor*0.05):
                clusters.append([row])
            else:
                group.append(row)
        for group in clusters:
            dates = sorted({dt.date.fromisoformat(r["date"]) for r in group})
            if len(dates) < 3:
                continue
            gaps = [(b-a).days for a, b in zip(dates, dates[1:])]
            for cadence, target, tolerance in [("weekly", 7, 2), ("monthly", 30, 4), ("annual", 365, 14)]:
                consistency = sum(abs(gap-target) <= tolerance for gap in gaps) / len(gaps)
                if consistency < 0.75 or abs(median(gaps)-target) > tolerance:
                    continue
                candidates.append({"description": group[0]["description"], "cadence": cadence,
                                   "amount_pence": int(median(-r["amount_pence"] for r in group)),
                                   "observations": len(dates), "record_count": len(group),
                                   "evidence_dates": [d.isoformat() for d in dates], "cadence_consistency": consistency,
                                   "day_tolerance": tolerance, "amount_tolerance_percent": 5, "minimum_amount_tolerance_pence": 1,
                                   "historical_next_date_estimate": (dates[-1]+dt.timedelta(days=target)).isoformat(),
                                   "uncertainty": "Historical regularity heuristic; no confirmed subscription or current obligation."})
                break
    return sorted(candidates, key=lambda x: (-x["observations"], x["description"]))[:100]
