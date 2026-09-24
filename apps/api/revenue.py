"""Revenue, cost, and time analytics for Luma.

Goal: know whether Luma is earning more than it costs in money and hours.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any


def money(value: Any) -> float:
    if value is None:
        return 0.0
    return float(Decimal(str(value)))


def revenue_summary(cur) -> dict:
    cur.execute("""
        SELECT
          COALESCE(SUM(CASE WHEN status='paid' THEN amount ELSE 0 END),0) AS paid_revenue,
          COALESCE(SUM(CASE WHEN status IN ('pending','paid') THEN amount ELSE 0 END),0) AS booked_revenue,
          COALESCE(SUM(CASE WHEN status='paid' THEN recurring_amount ELSE 0 END),0) AS recurring_revenue
        FROM revenue_transactions
    """)
    revenue = cur.fetchone()

    cur.execute("SELECT COALESCE(SUM(amount),0) AS costs FROM cost_records")
    costs = cur.fetchone()["costs"]

    cur.execute("""
        SELECT COUNT(*) AS won_projects,
               COALESCE(SUM(agreed_price),0) AS project_value
        FROM projects
        WHERE status NOT IN ('cancelled')
    """)
    projects = cur.fetchone()

    hours = 0.0
    try:
        cur.execute("SELECT COALESCE(SUM(hours),0) AS hours FROM time_entries")
        hours = money(cur.fetchone()["hours"])
    except Exception:
        hours = 0.0

    paid = money(revenue["paid_revenue"])
    total_cost = money(costs)
    return {
        "paid_revenue": paid,
        "booked_revenue": money(revenue["booked_revenue"]),
        "recurring_revenue": money(revenue["recurring_revenue"]),
        "costs": total_cost,
        "gross_contribution": paid - total_cost,
        "revenue_per_cost_dollar": (paid / total_cost) if total_cost else None,
        "won_projects": projects["won_projects"],
        "project_value": money(projects["project_value"]),
        "hours_logged": hours,
        "revenue_per_hour": (paid / hours) if hours else None,
        "contribution_per_hour": ((paid - total_cost) / hours) if hours else None,
    }


def service_performance(cur) -> list[dict]:
    cur.execute("""
        SELECT s.name AS service,
               COUNT(DISTINCT o.id) AS opportunities,
               COUNT(DISTINCT CASE WHEN o.status='won' THEN o.id END) AS won_opportunities,
               COALESCE((SELECT SUM(rt.amount) FROM revenue_transactions rt
                         JOIN projects rp ON rp.id=rt.project_id
                         WHERE rp.service_id=s.id AND rt.status='paid'),0) AS paid_revenue,
               COALESCE((SELECT SUM(cr.amount) FROM cost_records cr
                         JOIN projects cp ON cp.id=cr.project_id
                         WHERE cp.service_id=s.id),0) AS costs
        FROM services s
        LEFT JOIN opportunities o ON o.service_id=s.id
        GROUP BY s.id, s.name
        ORDER BY paid_revenue DESC, opportunities DESC
    """)
    rows = []
    for row in cur.fetchall():
        revenue = money(row["paid_revenue"])
        costs = money(row["costs"])
        rows.append({
            **row,
            "paid_revenue": revenue,
            "costs": costs,
            "contribution": revenue - costs,
            "revenue_per_cost_dollar": (revenue / costs) if costs else None,
        })
    return rows


def time_summary(cur, project_id: str | None = None) -> dict:
    if project_id:
        cur.execute(
            """SELECT COALESCE(SUM(hours),0) AS hours,
                      COUNT(*) AS entries
               FROM time_entries WHERE project_id=%s""",
            (project_id,),
        )
    else:
        cur.execute(
            """SELECT COALESCE(SUM(hours),0) AS hours,
                      COUNT(*) AS entries
               FROM time_entries"""
        )
    row = cur.fetchone()
    hours = money(row["hours"])
    cur.execute(
        """SELECT category, COALESCE(SUM(hours),0) AS hours
           FROM time_entries
           """
        + ("WHERE project_id=%s " if project_id else "")
        + "GROUP BY category ORDER BY hours DESC",
        ((project_id,) if project_id else ()),
    )
    by_category = [{"category": r["category"], "hours": money(r["hours"])} for r in cur.fetchall()]
    return {"hours": hours, "entries": row["entries"], "by_category": by_category}


def cost_breakdown(cur) -> dict:
    """Split costs into model/AI spend vs delivery/ops vs other."""
    try:
        cur.execute("""
            SELECT
              COALESCE(SUM(CASE WHEN category IN ('model','ai','llm','tokens') THEN amount ELSE 0 END),0) AS model_spend,
              COALESCE(SUM(CASE WHEN category IN ('delivery','labor','hosting','software') THEN amount ELSE 0 END),0) AS delivery_cost,
              COALESCE(SUM(CASE WHEN category NOT IN ('model','ai','llm','tokens','delivery','labor','hosting','software')
                                 OR category IS NULL THEN amount ELSE 0 END),0) AS other_cost,
              COALESCE(SUM(amount),0) AS total_cost
            FROM cost_records
        """)
        row = cur.fetchone() or {}
    except Exception:
        row = {"model_spend": 0, "delivery_cost": 0, "other_cost": 0, "total_cost": 0}
    paid = 0.0
    try:
        cur.execute("SELECT COALESCE(SUM(amount),0) AS paid FROM revenue_transactions WHERE status='paid'")
        paid = money(cur.fetchone()["paid"])
    except Exception:
        pass
    model = money(row.get("model_spend"))
    delivery = money(row.get("delivery_cost"))
    other = money(row.get("other_cost"))
    total = money(row.get("total_cost"))
    return {
        "model_spend": model,
        "delivery_cost": delivery,
        "other_cost": other,
        "total_cost": total,
        "paid_revenue": paid,
        "contribution_after_model": paid - model,
        "contribution_after_all_costs": paid - total,
        "revenue_per_model_dollar": (paid / model) if model else None,
        "revenue_per_delivery_dollar": (paid / delivery) if delivery else None,
    }
