"use client";

import { useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Project = { id: string; name: string; business_name: string; service_name?: string };
type Option = {
  key: string; label: string; type: "text" | "select" | "boolean"; required: boolean;
  placeholder?: string; options?: { value: string; label: string }[];
};
type Config = {
  project_id: string; service: string; definitions: Option[];
  selected: Record<string, any>; validation: { missing: string[]; complete: boolean };
  summary: { key: string; label: string; value: any; configured: boolean }[];
};

const inputStyle: React.CSSProperties = {
  width: "100%", boxSizing: "border-box", padding: "9px 10px",
  border: "1px solid #dbe3ee", borderRadius: 8, fontSize: 13, marginTop: 5,
};

const buttonStyle: React.CSSProperties = {
  padding: "9px 12px", borderRadius: 8, border: "1px solid #e2e8f0",
  background: "#fff", cursor: "pointer", fontWeight: 600, fontSize: 13,
};

export default function ProjectConfiguration({ projects }: { projects: Project[] }) {
  const [selected, setSelected] = useState(projects[0]?.id || "");
  const [config, setConfig] = useState<Config | null>(null);
  const [values, setValues] = useState<Record<string, any>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function load(projectId: string) {
    if (!projectId) return;
    const res = await fetch(API + "/projects/" + projectId + "/configuration");
    const data = await res.json();
    setConfig(data);
    setValues(data.selected || {});
  }

  useEffect(() => { load(selected).catch(() => setMessage("Could not load project configuration.")); }, [selected]);

  function setValue(key: string, value: any) {
    setValues(prev => ({ ...prev, [key]: value }));
  }

  async function save() {
    if (!selected) return;
    setBusy(true); setMessage("");
    try {
      const res = await fetch(API + "/projects/" + selected + "/configuration", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ options: values }),
      });
      const data = await res.json();
      if (!res.ok) { setMessage(data.detail || "Could not save configuration."); return; }
      setConfig(data); setValues(data.selected || {});
      setMessage(data.validation.complete ? "Project configuration is complete." : "Saved. Complete the remaining required options.");
    } catch { setMessage("Could not reach the API."); }
    finally { setBusy(false); }
  }

  const missingLabels = useMemo(() => {
    const map = new Map((config?.definitions || []).map(x => [x.key, x.label]));
    return (config?.validation.missing || []).map(k => map.get(k) || k);
  }, [config]);

  return (
    <section style={{ marginTop: 16, border: "1px solid #e8e8ec", borderRadius: 16, padding: 20, background: "#fff", boxShadow: "0 1px 2px rgba(15,23,42,0.04)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18 }}>Project Configuration / Options Center</h2>
          <p style={{ margin: "6px 0 0", color: "#64748b", fontSize: 13 }}>
            Configure the whole project before build. Options change with the service; nothing here assumes every project needs the same tools.
          </p>
        </div>
        {projects.length > 0 && (
          <select value={selected} onChange={e => setSelected(e.target.value)} style={{ ...inputStyle, width: 280, marginTop: 0 }}>
            {projects.map(p => <option key={p.id} value={p.id}>{p.business_name} — {p.name}</option>)}
          </select>
        )}
      </div>

      {!selected ? <p style={{ color: "#94a3b8" }}>Create a project to configure it.</p> : !config ? (
        <p style={{ color: "#94a3b8", marginBottom: 0 }}>Loading configuration…</p>
      ) : (
        <>
          <div style={{ marginTop: 16, padding: 12, borderRadius: 10, background: config.validation.complete ? "#ecfdf5" : "#f8fafc", border: "1px solid #e2e8f0" }}>
            <strong>{config.validation.complete ? "Configuration complete" : "Configuration needs a few choices"}</strong>
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
              {config.service} · {config.summary.filter(x => x.configured).length}/{config.summary.length} options configured
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12, marginTop: 16 }}>
            {config.definitions.map(option => (
              <label key={option.key} style={{ fontSize: 13, fontWeight: 600 }}>
                {option.label}{option.required ? " *" : ""}
                {option.type === "select" ? (
                  <select value={values[option.key] || ""} onChange={e => setValue(option.key, e.target.value)} style={inputStyle}>
                    <option value="">Choose…</option>
                    {(option.options || []).map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
                  </select>
                ) : option.type === "boolean" ? (
                  <select value={String(values[option.key] === true)} onChange={e => setValue(option.key, e.target.value === "true")} style={inputStyle}>
                    <option value="false">No / not yet</option><option value="true">Yes / confirmed</option>
                  </select>
                ) : (
                  <input value={values[option.key] || ""} onChange={e => setValue(option.key, e.target.value)} placeholder={option.placeholder || ""} style={inputStyle} />
                )}
              </label>
            ))}
          </div>

          {missingLabels.length > 0 && (
            <div style={{ marginTop: 14, fontSize: 13, color: "#92400e", background: "#fffbeb", border: "1px solid #fde68a", borderRadius: 8, padding: 10 }}>
              Still needed: {missingLabels.join(", ")}
            </div>
          )}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 16 }}>
            <button disabled={busy} onClick={save} style={{ ...buttonStyle, background: "#4f46e5", color: "#fff", border: "none" }}>
              {busy ? "Saving…" : "Save project configuration"}
            </button>
            {config.validation.complete && <span style={{ ...buttonStyle, background: "#ecfdf5", color: "#065f46" }}>✓ Ready for build planning</span>}
          </div>
          {message && <p style={{ fontSize: 13, color: "#475569" }}>{message}</p>}
        </>
      )}
    </section>
  );
}
