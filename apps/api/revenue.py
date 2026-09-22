"""Revenue and operating-cost analytics for the Luma MVP."""
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
