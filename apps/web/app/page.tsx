"use client";

import { useEffect, useState } from "react";
import LaunchCenter from "./launch-center";
import ClientTrustCenter from "./client-trust-center";
import ProjectConfiguration from "./project-configuration";
import RevenueAnalytics from "./revenue-analytics";
import IntegrationCenter from "./integration-center";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Dashboard = {
  businesses: number;
  opportunities: number;
  proposals: number;
  clients: number;
  projects: number;
  open_tasks: number;
  pipeline_value: number;
  won_revenue: number;
  opportunities_queue: any[];
  active_projects: any[];
  tasks: any[];
  research_queue: any[];
  outreach_drafts: any[];
};

const money = (value: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value || 0);

const card: React.CSSProperties = {
  border: "1px solid #e8e8ec",
  borderRadius: 16,
  padding: 20,
  background: "#fff",
  boxShadow: "0 1px 2px rgba(15,23,42,0.04)",
};

const smallButton: React.CSSProperties = {
  padding: "7px 10px",
  borderRadius: 8,
  border: "1px solid #e2e8f0",
  background: "#fff",
  cursor: "pointer",
  fontWeight: 600,
  fontSize: 12,
  color: "#334155",
};

const badge: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  padding: "4px 10px",
  borderRadius: 999,
  background: "#eef2ff",
  color: "#3730a3",
  border: "1px solid #c7d2fe",
  display: "inline-block",
};

export default function Home() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  async function load() {
    const response = await fetch(API + "/dashboard");
    setData(await response.json());
  }

  useEffect(() => {
    load().catch(() => setData(null));
  }, []);

  async function taskStatus(id: string, status: string) {
    setBusy(id);
    try {
      await fetch(API + "/tasks/" + id + "/status", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      await load();
    } finally {
      setBusy(null);
    }
  }

  async function runJsonAction(label: string, path: string, body: unknown) {
    setBusy(path);
    setActionMsg(null);
    try {
      const res = await fetch(API + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setActionMsg(err.detail || "Something went wrong. Try again.");
        return;
      }
      setActionMsg(label + " complete — refresh to see the delivery state.");
      await load();
    } catch {
      setActionMsg("Could not reach the API. Is it running?");
    } finally {
      setBusy(null);
    }
  }

  async function runAction(label: string, path: string) {
    setBusy(path);
    setActionMsg(null);
    try {
      const res = await fetch(API + path, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setActionMsg(err.detail || "Something went wrong. Try again.");
        return;
      }
      setActionMsg(label + " ready — refresh to see updates.");
      await load();
    } catch {
      setActionMsg("Could not reach the API. Is it running?");
    } finally {
      setBusy(null);
    }
  }

  const d = data || {
    businesses: 0,
    opportunities: 0,
    proposals: 0,
    clients: 0,
    projects: 0,
    open_tasks: 0,
    pipeline_value: 0,
    won_revenue: 0,
    opportunities_queue: [],
    active_projects: [],
    tasks: [],
    research_queue: [],
    outreach_drafts: [],
  };

  return (
    <main
      style={{
        padding: "28px 24px 48px",
        maxWidth: 1120,
        margin: "0 auto",
        fontFamily:
          'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
        color: "#0f172a",
        background: "#f8fafc",
        minHeight: "100vh",
      }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 16,
          marginBottom: 8,
        }}
      >
        <div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              marginBottom: 6,
            }}
          >
            <img src="/icon.svg" alt="Luma" width={28} height={28} style={{borderRadius: 8}} />
            <span
              style={{
                fontSize: 13,
                fontWeight: 600,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                color: "#6366f1",
              }}
            >
              Luma
            </span>
          </div>
          <h1 style={{ margin: "0 0 8px", fontSize: 28, fontWeight: 700 }}>
            Only recommend what you observed
          </h1>
          <p style={{ margin: 0, color: "#64748b", maxWidth: 560, lineHeight: 1.5 }}>
            Research a site, turn signals into service opportunities, sell the work,
            generate the implementation, validate it, and prepare launch and handoff.
            Nothing external sends or deploys without approval.
          </p>
        </div>
        <button
          onClick={() => load()}
          style={{
            padding: "10px 16px",
            borderRadius: 10,
            border: "1px solid #e2e8f0",
            background: "#fff",
            cursor: "pointer",
            fontWeight: 600,
            color: "#334155",
          }}
        >
          Refresh
        </button>
      </header>

      {actionMsg && (
        <div
          style={{
            marginTop: 16,
            padding: "12px 14px",
            borderRadius: 10,
            background: "#ecfdf5",
            color: "#065f46",
            border: "1px solid #a7f3d0",
            fontSize: 14,
          }}
        >
          {actionMsg}
        </div>
      )}

      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))",
          gap: 12,
          marginTop: 24,
        }}
      >
        {[
          ["Pipeline", money(d.pipeline_value)],
          ["Won", money(d.won_revenue)],
          ["Opportunities", d.opportunities],
          ["Proposals", d.proposals],
          ["Clients", d.clients],
          ["Projects", d.projects],
          ["Open tasks", d.open_tasks],
          ["Prospects", d.businesses],
        ].map(([label, value]) => (
          <div key={String(label)} style={card}>
            <div
              style={{
                fontSize: 12,
                textTransform: "uppercase",
                letterSpacing: "0.03em",
                color: "#94a3b8",
                fontWeight: 600,
              }}
            >
              {label}
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, marginTop: 6 }}>{value}</div>
          </div>
        ))}
      </section>

      <section
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0,1.4fr) minmax(0,1fr)",
          gap: 16,
          marginTop: 24,
        }}
      >
        <div style={card}>
          <h2 style={{ marginTop: 0, fontSize: 18 }}>Opportunities to act on</h2>
          <p style={{ marginTop: -6, color: "#64748b", fontSize: 14 }}>
            Each row is a specific service tied to evidence — not a generic “AI” pitch.
          </p>
          {d.opportunities_queue.length === 0 ? (
            <p style={{ color: "#94a3b8" }}>No open opportunities yet. Research a prospect to start.</p>
          ) : (
            d.opportunities_queue.map((o) => (
              <div
                key={o.id}
                style={{
                  padding: "16px 0",
                  borderTop: "1px solid #f1f5f9",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    alignItems: "center",
                  }}
                >
                  <strong style={{ fontSize: 15 }}>{o.business_name}</strong>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#475569" }}>
                    Score {o.score ?? "—"}
                  </span>
                </div>
                <div style={{ marginTop: 6, color: "#334155" }}>{o.title}</div>
                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 8,
                    alignItems: "center",
                    marginTop: 10,
                  }}
                >
                  <span style={badge}>{o.service_name || "Unassigned"}</span>
                  <span style={{ fontSize: 13, color: "#64748b" }}>
                    {money(o.estimated_value_min)}–{money(o.estimated_value_max)}
                  </span>
                </div>
                <div style={{ fontSize: 13, marginTop: 10, color: "#64748b" }}>
                  Next: {o.next_action || "Review evidence"}
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
                  <button
                    disabled={busy === o.id + "-brief"}
                    onClick={() =>
                      runAction("Client brief", "/opportunities/" + o.id + "/client-brief")
                    }
                    style={{
                      padding: "8px 12px",
                      borderRadius: 8,
                      border: "none",
                      background: "#4f46e5",
                      color: "#fff",
                      fontWeight: 600,
                      fontSize: 13,
                      cursor: "pointer",
                    }}
                  >
                    Client brief
                  </button>
                  <button
                    disabled={busy === o.id + "-outreach"}
                    onClick={() =>
                      runAction("Outreach sequence", "/outreach/drafts?opportunity_id=" + o.id)
                    }
                    style={{
                      padding: "8px 12px",
                      borderRadius: 8,
                      border: "1px solid #e2e8f0",
                      background: "#fff",
                      fontWeight: 600,
                      fontSize: 13,
                      cursor: "pointer",
                      color: "#334155",
                    }}
                  >
                    Draft outreach
                  </button>
                  <button
                    disabled={busy === o.id + "-call"}
                    onClick={() =>
                      runAction("Call prep", "/opportunities/" + o.id + "/prepare-call")
                    }
                    style={{
                      padding: "8px 12px",
                      borderRadius: 8,
                      border: "1px solid #e2e8f0",
                      background: "#fff",
                      fontWeight: 600,
                      fontSize: 13,
                      cursor: "pointer",
                      color: "#334155",
                    }}
                  >
                    Call prep
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={card}>
            <h2 style={{ marginTop: 0, fontSize: 18 }}>Active projects</h2>
            {d.active_projects.length === 0 ? (
              <p style={{ color: "#94a3b8" }}>No active projects yet.</p>
            ) : (
              d.active_projects.map((p) => (
                <div
                  key={p.id}
                  style={{ padding: "12px 0", borderTop: "1px solid #f1f5f9" }}
                >
                  <strong>{p.business_name}</strong>
                  <div style={{ color: "#334155" }}>{p.name}</div>
                  <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>
                    {p.status} · {money(p.agreed_price)}
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
                    <span style={badge}>Build: {p.implementation_status || "requirements"}</span>
                    {p.validated_at && <span style={badge}>QA passed</span>}
                    {p.approved_at && <span style={badge}>Approved</span>}
                    {p.handoff_status && <span style={badge}>Handoff: {p.handoff_status}</span>}
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
                    {(!p.implementation_status || p.implementation_status === "requirements" || p.implementation_status === "changes_requested" || p.implementation_status === "failed") && (
                      <button onClick={() => runAction("Implementation", "/projects/" + p.id + "/generate")} style={smallButton}>Generate</button>
                    )}
                    {p.implementation_status === "generated" && (
                      <button onClick={() => runAction("QA", "/projects/" + p.id + "/validate")} style={smallButton}>Run QA</button>
                    )}
                    {p.implementation_status === "validated" && (
                      <button onClick={() => runJsonAction("Approval", "/projects/" + p.id + "/approval", { approved: true })} style={smallButton}>Approve</button>
                    )}
                    {p.implementation_status === "approved" && (
                      <button onClick={() => runAction("Deployment", "/projects/" + p.id + "/deploy")} style={smallButton}>Deploy</button>
                    )}
                    {(p.implementation_status === "approved" || p.implementation_status === "deployed") && (
                      <button onClick={() => runAction("Handoff", "/projects/" + p.id + "/handoff")} style={smallButton}>Handoff</button>
                    )}
                    {p.implementation_status === "deployed" && (
                      <button onClick={() => runAction("Production check", "/projects/" + p.id + "/monitor")} style={smallButton}>Check live</button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          <div style={card}>
            <h2 style={{ marginTop: 0, fontSize: 18 }}>Research queue</h2>
            {d.research_queue.length === 0 ? (
              <p style={{ color: "#94a3b8" }}>Nothing waiting to research.</p>
            ) : (
              d.research_queue.map((r) => (
                <div
                  key={r.id}
                  style={{ padding: "12px 0", borderTop: "1px solid #f1f5f9" }}
                >
                  <strong>{r.business_name}</strong>
                  <div style={{ fontSize: 13, color: "#64748b" }}>
                    {r.website_url} · priority {r.priority}
                  </div>
                </div>
              ))
            )}
          </div>

          <div style={card}>
            <h2 style={{ marginTop: 0, fontSize: 18 }}>Outreach drafts</h2>
            <p style={{ marginTop: -6, color: "#64748b", fontSize: 13 }}>
              Human approval required before anything is sent.
            </p>
            {d.outreach_drafts.length === 0 ? (
              <p style={{ color: "#94a3b8" }}>No drafts waiting.</p>
            ) : (
              d.outreach_drafts.slice(0, 8).map((m) => (
                <div
                  key={m.id}
                  style={{ padding: "12px 0", borderTop: "1px solid #f1f5f9" }}
                >
                  <strong>{m.business_name || "Prospect"}</strong>
                  <div style={{ fontSize: 13, color: "#334155", marginTop: 2 }}>
                    {m.subject}
                  </div>
                  <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>
                    {m.status} · {m.channel}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      <section style={{ marginTop: 24 }}>
        <div style={card}>
          <h2 style={{ marginTop: 0, fontSize: 18 }}>Luma modules</h2>
          <p style={{ color: "#64748b", fontSize: 14 }}>Launch Center is one module. The operating system also includes research, opportunities, sales, projects, delivery, handoff, and revenue measurement.</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 10 }}>
            {[
              ["Discover / Research", "Find and investigate prospects"],
              ["Opportunities", "Evidence-backed service candidates"],
              ["Sales / Proposals", "Turn opportunities into approved work"],
              ["Projects", "Requirements, tasks, and delivery state"],
              ["Build / Delivery", "Generate, validate, package, deploy"],
              ["Client Launch Center", "Choose the right launch path"],
              ["Handoff", "Package and close the engagement"],
              ["Analytics / Revenue", "Measure pipeline and earned revenue"],
            ].map(([title, description]) => (
              <div key={title} style={{ padding: 14, border: "1px solid #e2e8f0", borderRadius: 12 }}>
                <div style={{ fontWeight: 700, fontSize: 14 }}>{title}</div>
                <div style={{ color: "#64748b", fontSize: 12, marginTop: 5 }}>{description}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <ClientTrustCenter />

      <ProjectConfiguration projects={d.active_projects} />

      <IntegrationCenter projects={d.active_projects} />

      <RevenueAnalytics />

      <LaunchCenter projects={d.active_projects} />

      <section style={{ ...card, marginTop: 16 }}>
        <h2 style={{ marginTop: 0, fontSize: 18 }}>Open tasks</h2>
        {d.tasks.length === 0 ? (
          <p style={{ color: "#94a3b8" }}>No open tasks.</p>
        ) : (
          d.tasks.map((t) => (
            <div
              key={t.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
                alignItems: "center",
                padding: "12px 0",
                borderTop: "1px solid #f1f5f9",
              }}
            >
              <div>
                <strong>{t.title}</strong>
                <div style={{ fontSize: 13, color: "#64748b" }}>{t.status}</div>
              </div>
              <button
                disabled={busy === t.id}
                onClick={() => taskStatus(t.id, "done")}
                style={{
                  padding: "8px 12px",
                  borderRadius: 8,
                  border: "1px solid #e2e8f0",
                  background: "#fff",
                  cursor: "pointer",
                  fontWeight: 600,
                  fontSize: 13,
                }}
              >
                Mark done
              </button>
            </div>
          ))
        )}
      </section>

      <footer
        style={{
          marginTop: 32,
          paddingTop: 16,
          borderTop: "1px solid #e2e8f0",
          color: "#94a3b8",
          fontSize: 13,
          lineHeight: 1.5,
        }}
      >
        <strong style={{ color: "#64748b" }}>How Luma is different:</strong> we map
        observed website signals to specific services, write outreach in plain
        language, and never send without your approval. Clients get a short brief —
        not a feature dump.
      </footer>
    </main>
  );
}
