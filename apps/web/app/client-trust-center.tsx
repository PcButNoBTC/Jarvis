"use client";

import React, { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Playbook = {
  id: string;
  region_key: string;
  display_name: string;
  status: string;
  proven_offers?: unknown[];
  industry_patterns?: unknown[];
};

export default function ClientTrustCenter() {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);

  useEffect(() => {
    fetch(API + "/regional-playbooks")
      .then((r) => (r.ok ? r.json() : []))
      .then(setPlaybooks)
      .catch(() => setPlaybooks([]));
  }, []);

  const card: React.CSSProperties = {
    border: "1px solid #e2e8f0",
    borderRadius: 14,
    padding: 18,
    background: "#fff",
  };

  return (
    <section style={{ marginTop: 24 }}>
      <div style={card}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start" }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 18 }}>Client trust &amp; growth controls</h2>
            <p style={{ margin: "6px 0 0", color: "#64748b", fontSize: 14, maxWidth: 700 }}>
              Luma is designed to earn expansion through useful results, not pressure.
              Opportunities need evidence and fit review, declined businesses can be suppressed,
              and new offers should follow demonstrated client value.
            </p>
          </div>
          <span style={{ fontSize: 12, fontWeight: 700, padding: "5px 9px", borderRadius: 999, background: "#ecfdf5", color: "#047857" }}>
            Trust-first
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 10, marginTop: 16 }}>
          {[
            ["Diagnose first", "Show observable evidence before recommending a service."],
            ["Smallest useful fix", "Prefer the simplest solution that can address the documented problem."],
            ["No-pressure outreach", "Respect declines, complaints, and contact limits."],
            ["Client control", "Keep consequential actions and production changes approval-gated."],
            ["Measure outcomes", "Track baseline and current results before proposing expansion."],
            ["Local reputation", "Protect the reputation of each pilot region before scaling."],
          ].map(([title, body]) => (
            <div key={title} style={{ padding: 13, border: "1px solid #e2e8f0", borderRadius: 10 }}>
              <div style={{ fontWeight: 700, fontSize: 14 }}>{title}</div>
              <div style={{ marginTop: 5, color: "#64748b", fontSize: 12, lineHeight: 1.45 }}>{body}</div>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 18, padding: 14, borderRadius: 10, background: "#f8fafc" }}>
          <strong style={{ fontSize: 14 }}>Client-facing promise</strong>
          <p style={{ margin: "6px 0 0", color: "#475569", fontSize: 13, lineHeight: 1.5 }}>
            “We will show you what we observed, explain why it may matter, give you options,
            and let you decide. If we do not think automation is appropriate, we will say so.”
          </p>
        </div>

        <div style={{ marginTop: 18 }}>
          <div style={{ fontWeight: 700, fontSize: 14 }}>Regional pilots</div>
          {playbooks.length === 0 ? (
            <p style={{ color: "#94a3b8", fontSize: 13 }}>
              No regional playbooks yet. Create one after the local pilot has enough evidence to document what actually works.
            </p>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 10, marginTop: 10 }}>
              {playbooks.map((p) => (
                <div key={p.id} style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 12 }}>
                  <strong>{p.display_name}</strong>
                  <div style={{ color: "#64748b", fontSize: 12, marginTop: 4 }}>{p.status}</div>
                  <div style={{ color: "#64748b", fontSize: 12, marginTop: 6 }}>
                    {p.proven_offers?.length || 0} proven offers · {p.industry_patterns?.length || 0} documented patterns
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
