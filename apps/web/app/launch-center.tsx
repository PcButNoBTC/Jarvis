"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Project = { id: string; name: string; business_name: string; service_name?: string };
type Readiness = {
  ready: boolean;
  service: string;
  checklist: { key: string; label: string; required: boolean; complete: boolean; help: string }[];
  settings: Record<string, any>;
  suggestions: { category: string; name: string; url: string; reason: string }[];
  launch_options: { key: string; name: string; category: string; description: string }[];
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "9px 10px",
  border: "1px solid #dbe3ee",
  borderRadius: 8,
  fontSize: 13,
  marginTop: 5,
};

const buttonStyle: React.CSSProperties = {
  padding: "9px 12px",
  borderRadius: 8,
  border: "1px solid #e2e8f0",
  background: "#fff",
  cursor: "pointer",
  fontWeight: 600,
  fontSize: 13,
};

export default function LaunchCenter({ projects }: { projects: Project[] }) {
  const [selected, setSelected] = useState<string>(projects[0]?.id || "");
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [settings, setSettings] = useState<Record<string, any>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!selected) return;
    fetch(API + "/projects/" + selected + "/launch-readiness")
      .then(r => r.json())
      .then((data: Readiness) => {
        setReadiness(data);
        setSettings(data.settings || {});
      })
      .catch(() => setMessage("Could not load launch requirements."));
  }, [selected]);

  function set(key: string, value: any) {
    setSettings(prev => ({ ...prev, [key]: value }));
  }

  async function save() {
    if (!selected) return;
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(API + "/projects/" + selected + "/launch-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ settings }),
      });
      const data = await response.json();
      if (!response.ok) {
        setMessage(data.detail || "Could not save launch settings.");
        return;
      }
      setReadiness(data);
      setSettings(data.settings || {});
      setMessage(data.ready ? "Launch requirements are complete." : "Saved. Complete the remaining required items before launch.");
    } catch {
      setMessage("Could not reach the API.");
    } finally {
      setBusy(false);
    }
  }

  const checklist = readiness?.checklist || [];
  const completed = checklist.filter(x => x.complete).length;

  return (
    <section style={{ marginTop: 16, border: "1px solid #e8e8ec", borderRadius: 16, padding: 20, background: "#fff", boxShadow: "0 1px 2px rgba(15,23,42,0.04)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18 }}>Client Launch Center</h2>
          <p style={{ margin: "6px 0 0", color: "#64748b", fontSize: 13 }}>
            The client supplies or confirms the production details. Luma will not mark a project launch-ready until the required items are complete.
          </p>
        </div>
        {projects.length > 0 && (
          <select value={selected} onChange={e => setSelected(e.target.value)} style={{ ...inputStyle, width: 260, marginTop: 0 }}>
            {projects.map(p => <option key={p.id} value={p.id}>{p.business_name} — {p.name}</option>)}
          </select>
        )}
      </div>

      {!selected ? (
        <p style={{ color: "#94a3b8", marginBottom: 0 }}>Create a project to configure launch.</p>
      ) : (
        <>
          <div style={{ marginTop: 16, padding: 12, borderRadius: 10, background: readiness?.ready ? "#ecfdf5" : "#f8fafc", border: "1px solid #e2e8f0" }}>
            <strong>{readiness?.ready ? "Ready for launch review" : "Launch is blocked until requirements are complete"}</strong>
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
              {completed}/{checklist.length} checklist items complete · {readiness?.service || "Project"}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12, marginTop: 16 }}>
            <label>Launch path
              <select value={settings.launch_mode || "prepare_and_client_launch"} onChange={e => set("launch_mode", e.target.value)} style={inputStyle}>
                <option value="prepare_and_client_launch">Prepare package for client launch</option>
                <option value="luma_deploy">Luma deploys after approval</option>
              </select>
            </label>
            <label>Hosting / deployment option
              <select value={settings.hosting_option || ""} onChange={e => set("hosting_option", e.target.value)} style={inputStyle}>
                <option value="">Choose an option</option>
                {(readiness?.launch_options || []).map(o => <option key={o.key} value={o.key}>{o.name}</option>)}
              </select>
            </label>
            <label>Custom provider / target
              <input value={settings.hosting_provider || ""} onChange={e => set("hosting_provider", e.target.value)} placeholder="Only for custom hosting" style={inputStyle} />
            </label>
            {readiness?.service === "AI Website" && <label>Production domain
              <input value={settings.domain || ""} onChange={e => set("domain", e.target.value)} placeholder="example.com" style={inputStyle} />
            </label>}
            {settings.launch_mode === "luma_deploy" && <label>Hosting access confirmed
              <select value={String(!!settings.hosting_access)} onChange={e => set("hosting_access", e.target.value === "true")} style={inputStyle}>
                <option value="false">Not yet</option><option value="true">Confirmed</option>
              </select>
            </label>}
            {readiness?.service === "AI Website" && settings.launch_mode === "luma_deploy" && <label>DNS access confirmed
              <select value={String(!!settings.dns_access)} onChange={e => set("dns_access", e.target.value === "true")} style={inputStyle}>
                <option value="false">Not yet</option><option value="true">Confirmed</option>
              </select>
            </label>}
            {readiness?.service === "AI Website" && settings.launch_mode === "luma_deploy" && <label>HTTPS / SSL confirmed
              <select value={String(!!settings.ssl_ready)} onChange={e => set("ssl_ready", e.target.value === "true")} style={inputStyle}>
                <option value="false">Not yet</option><option value="true">Confirmed</option>
              </select>
            </label>}
            <label>Primary contact email
              <input value={settings.contact_email || ""} onChange={e => set("contact_email", e.target.value)} placeholder="client@example.com" style={inputStyle} />
            </label>
            {readiness?.service === "AI Website" && settings.launch_mode === "luma_deploy" && <label>Production URL
              <input value={settings.production_url || ""} onChange={e => set("production_url", e.target.value)} placeholder="https://example.com" style={inputStyle} />
            </label>}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12, marginTop: 12 }}>
            {readiness?.service === "AI Website" ? <label>Approved production copy/assets
              <select value={String(!!settings.content_approved)} onChange={e => set("content_approved", e.target.value === "true")} style={inputStyle}>
                <option value="false">Not yet</option><option value="true">Approved</option>
              </select>
            </label> : <label>Requirements approved
              <select value={String(!!settings.requirements_approved)} onChange={e => set("requirements_approved", e.target.value === "true")} style={inputStyle}>
                <option value="false">Not yet</option><option value="true">Approved</option>
              </select>
            </label>}
            {readiness?.service && readiness.service !== "AI Website" && <label>Provider / platform
              <input value={settings.provider_selected || ""} onChange={e => set("provider_selected", e.target.value)} placeholder="Calendar, CRM, phone system, etc." style={inputStyle} />
            </label>}
            {readiness?.service && readiness.service !== "AI Website" && <label>Credentials/access confirmed
              <select value={String(!!settings.credentials_ready)} onChange={e => set("credentials_ready", e.target.value === "true")} style={inputStyle}>
                <option value="false">Not yet</option><option value="true">Confirmed</option>
              </select>
            </label>}
            {readiness?.service && readiness.service !== "AI Website" && <label>Production test approved
              <select value={String(!!settings.test_approved)} onChange={e => set("test_approved", e.target.value === "true")} style={inputStyle}>
                <option value="false">Not yet</option><option value="true">Approved</option>
              </select>
            </label>}
            <label>Privacy policy URL
              <input value={settings.privacy_url || ""} onChange={e => set("privacy_url", e.target.value)} placeholder="https://example.com/privacy" style={inputStyle} />
            </label>
            <label>Terms URL (if applicable)
              <input value={settings.terms_url || ""} onChange={e => set("terms_url", e.target.value)} placeholder="https://example.com/terms" style={inputStyle} />
            </label>
            <label>Analytics / measurement
              <input value={settings.analytics || ""} onChange={e => set("analytics", e.target.value)} placeholder="GA4, Plausible, none, etc." style={inputStyle} />
            </label>
          </div>

          {readiness?.launch_options?.length ? <div style={{ marginTop: 18 }}>
            <h3 style={{ fontSize: 15, marginBottom: 8 }}>Available launch options</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
              {readiness.launch_options.map(o => <button key={o.key} onClick={() => set("hosting_option", o.key)} style={{ ...buttonStyle, textAlign: "left" }}>
                <strong>{o.name}</strong><div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>{o.description}</div>
              </button>)}
            </div>
          </div> : null}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 16 }}>
            <button disabled={busy} onClick={save} style={{ ...buttonStyle, background: "#4f46e5", color: "#fff", border: "none" }}>
              {busy ? "Saving…" : "Save launch settings"}
            </button>
            {readiness?.ready && <span style={{ ...buttonStyle, background: "#ecfdf5", color: "#065f46" }}>✓ Required items complete</span>}
          </div>

          {message && <p style={{ fontSize: 13, color: "#475569" }}>{message}</p>}

          {checklist.length > 0 && (
            <div style={{ marginTop: 18 }}>
              <h3 style={{ fontSize: 15, marginBottom: 8 }}>Launch checklist</h3>
              {checklist.map(item => (
                <div key={item.key} style={{ display: "flex", gap: 10, padding: "9px 0", borderTop: "1px solid #f1f5f9", fontSize: 13 }}>
                  <span>{item.complete ? "✓" : "○"}</span>
                  <div><strong>{item.label}</strong><div style={{ color: "#64748b", marginTop: 2 }}>{item.help}</div></div>
                </div>
              ))}
            </div>
          )}

          {readiness?.suggestions?.length ? (
            <div style={{ marginTop: 18 }}>
              <h3 style={{ fontSize: 15, marginBottom: 8 }}>Suggested resources</h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
                {readiness.suggestions.map(s => (
                  <a key={s.name} href={s.url} target="_blank" rel="noreferrer" style={{ textDecoration: "none", color: "#0f172a", border: "1px solid #e2e8f0", borderRadius: 10, padding: 12 }}>
                    <strong>{s.name}</strong>
                    <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>{s.category}</div>
                    <div style={{ fontSize: 12, color: "#475569", marginTop: 6 }}>{s.reason}</div>
                  </a>
                ))}
              </div>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
