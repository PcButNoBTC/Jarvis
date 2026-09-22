"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Project = { id: string; name: string; business_name: string; service_name?: string };
type Provider = { provider: string; capabilities: string[] };
type Suggestion = { category: string; reason: string; providers: Provider[] };

export default function IntegrationCenter({ projects }: { projects: Project[] }) {
  const [projectId, setProjectId] = useState(projects[0]?.id || "");
  const [service, setService] = useState(projects[0]?.service_name || "");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [connections, setConnections] = useState<any[]>([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const project = projects.find(p => p.id === projectId);
    setService(project?.service_name || "");
  }, [projectId, projects]);

  async function load() {
    if (!projectId) return;
    const [s, c] = await Promise.all([
      fetch(API + "/integrations/suggestions/" + encodeURIComponent(service)).then(r => r.json()),
      fetch(API + "/integrations?project_id=" + encodeURIComponent(projectId)).then(r => r.json()),
    ]);
    setSuggestions(s.suggestions || []);
    setConnections(c || []);
  }

  useEffect(() => { load().catch(() => setMessage("Could not load integrations.")); }, [projectId, service]);

  async function choose(category: string, provider: string) {
    setMessage("");
    const res = await fetch(API + "/integrations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId, category, provider }),
    });
    const data = await res.json();
    if (!res.ok) { setMessage(data.detail || "Could not create connection."); return; }
    setMessage(provider + " is selected. Luma will not treat it as connected until verification succeeds.");
    await load();
  }

  const featured = suggestions.filter(x => ["calendar", "phone", "crm"].includes(x.category));

  return (
    <section style={{ marginTop: 16, border: "1px solid #e8e8ec", borderRadius: 16, padding: 20, background: "#fff", boxShadow: "0 1px 2px rgba(15,23,42,0.04)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18 }}>Integration Center</h2>
          <p style={{ margin: "6px 0 0", color: "#64748b", fontSize: 13 }}>
            Choose a provider, bring an existing system, or let Luma recommend. Selection never equals authorization.
          </p>
        </div>
        {projects.length > 0 && <select value={projectId} onChange={e => setProjectId(e.target.value)} style={{ padding: "9px 10px", border: "1px solid #dbe3ee", borderRadius: 8, width: 280 }}>
          {projects.map(p => <option key={p.id} value={p.id}>{p.business_name} — {p.name}</option>)}
        </select>}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(230px,1fr))", gap: 12, marginTop: 16 }}>
        {featured.map(group => (
          <div key={group.category} style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: 14 }}>
            <strong style={{ textTransform: "capitalize" }}>{group.category}</strong>
            <p style={{ fontSize: 12, color: "#64748b", minHeight: 34 }}>{group.reason}</p>
            <div style={{ display: "grid", gap: 7 }}>
              {group.providers.map(p => (
                <button key={p.provider} onClick={() => choose(group.category, p.provider)} style={{ textAlign: "left", padding: "8px 10px", borderRadius: 8, border: "1px solid #e2e8f0", background: "#f8fafc", cursor: "pointer" }}>
                  <strong>{p.provider.replaceAll("_", " ")}</strong>
                  <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>{p.capabilities.join(" · ")}</div>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {suggestions.length === 0 && <p style={{ color: "#64748b", fontSize: 13 }}>No extra provider is required for this service yet.</p>}

      {connections.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <strong>Project connections</strong>
          <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
            {connections.map(c => (
              <div key={c.id} style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: 10, border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 13 }}>
                <span><strong>{c.category}</strong> · {c.provider}</span>
                <span style={{ color: c.status === "verified" ? "#047857" : "#92400e" }}>{c.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {message && <p style={{ fontSize: 13, color: "#475569", marginBottom: 0 }}>{message}</p>}
    </section>
  );
}
