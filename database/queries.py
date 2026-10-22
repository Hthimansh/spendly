from database.db import get_db
from datetime import datetime


def _date_where(user_id, date_from, date_to):
    clauses = ["user_id = ?"]
    params  = [user_id]
    if date_from:
        clauses.append("date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("date <= ?")
        params.append(date_to)
    return " AND ".join(clauses), params


def get_user_by_id(user_id):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def get_recent_transactions(user_id, date_from=None, date_to=None):
    where, params = _date_where(user_id, date_from, date_to)
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT id, date, description, category, amount "
            f"FROM expenses WHERE {where} ORDER BY date DESC",
            params
        ).fetchall()
    result = []
    for r in rows:
        d = datetime.strptime(r["date"], "%Y-%m-%d")
        result.append({
            "id":          r["id"],
            "date":        d.strftime("%b %d"),
            "description": r["description"],
            "category":    r["category"],
            "amount":      f"₹{r['amount']:.2f}",
        })
    return result


def get_summary_stats(user_id, date_from=None, date_to=None):
    where, params = _date_where(user_id, date_from, date_to)
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT amount, category FROM expenses WHERE {where}",
            params
        ).fetchall()
    if not rows:
        return {"total_spent": "₹0.00", "transaction_count": 0, "top_category": "—"}
    total = sum(r["amount"] for r in rows)
    cat_totals = {}
    for r in rows:
        cat_totals[r["category"]] = cat_totals.get(r["category"], 0) + r["amount"]
    top = max(cat_totals, key=cat_totals.get)
    return {
        "total_spent":       f"₹{total:.2f}",
        "transaction_count": len(rows),
        "top_category":      top,
    }


def get_category_breakdown(user_id, date_from=None, date_to=None):
    where, params = _date_where(user_id, date_from, date_to)
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT amount, category FROM expenses WHERE {where}",
            params
        ).fetchall()
    if not rows:
        return []
    cat_totals = {}
    for r in rows:
        cat_totals[r["category"]] = cat_totals.get(r["category"], 0) + r["amount"]
    grand = sum(cat_totals.values())
    breakdown = sorted(
        [{"name": k, "raw": v} for k, v in cat_totals.items()],
        key=lambda x: x["raw"], reverse=True
    )
    result = [{"name": c["name"], "amount": f"₹{c['raw']:.2f}",
               "pct": round(c["raw"] / grand * 100)} for c in breakdown]
    diff = 100 - sum(c["pct"] for c in result)
    if result:
        result[0]["pct"] += diff
    return result
