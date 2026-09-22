"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Analytics = {
  summary: {
    paid_revenue: number;
    booked_revenue: number;
    recurring_revenue: number;
    costs: number;
    gross_contribution: number;
    revenue_per_cost_dollar: number | null;
  };
  services: Array<{
    service: string;
    opportunities: number;
    won_opportunities: number;
    paid_revenue: number;
    costs: number;
    contribution: number;
  }>;
};

const money = (value: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value || 0);

export default function RevenueAnalytics() {
  const [data, setData] = useState<Analytics | null>(null);

  useEffect(() => {
    fetch(API + "/analytics/revenue").then((r) => r.ok ? r.json() : null).then(setData).catch(() => setData(null));
  }, []);

  if (!data) return null;

  return (
    <section style={{ marginTop: 24, border: "1px solid #e8e8ec", borderRadius: 16, padding: 20, background: "#fff" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18 }}>Revenue / operating economics</h2>
          <p style={{ margin: "6px 0 0", color: "#64748b", fontSize: 13 }}>
            Revenue is measured against recorded Luma and delivery costs.
          </p>
        </div>
        <div style={{ fontWeight: 700 }}>
          {data.summary.revenue_per_cost_dollar == null ? "—" : data.summary.revenue_per_cost_dollar.toFixed(1) + "x revenue / cost"}
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 12, marginTop: 16 }}>
        {[
          ["Paid revenue", money(data.summary.paid_revenue)],
          ["Booked", money(data.summary.booked_revenue)],
          ["Costs", money(data.summary.costs)],
          ["Contribution", money(data.summary.gross_contribution)],
        ].map(([label, value]) => (
          <div key={label} style={{ padding: 14, borderRadius: 12, background: "#f8fafc" }}>
            <div style={{ fontSize: 12, color: "#64748b" }}>{label}</div>
            <div style={{ fontSize: 20, fontWeight: 700, marginTop: 4 }}>{value}</div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 18 }}>
        {data.services.map((service) => (
          <div key={service.service} style={{ display: "grid", gridTemplateColumns: "1.5fr repeat(3,1fr)", gap: 10, padding: "9px 0", borderTop: "1px solid #f1f5f9", fontSize: 13 }}>
            <strong>{service.service}</strong>
            <span>{service.opportunities} opps</span>
            <span>{money(service.paid_revenue)} revenue</span>
            <span>{money(service.contribution)} contribution</span>
          </div>
        ))}
      </div>
    </section>
  );
}
