"use client";

import { useEffect, useState } from "react";

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
};

const money = (value: number) => new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", maximumFractionDigits: 0
}).format(value || 0);

export default function Home() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    const response = await fetch(API + "/dashboard");
    setData(await response.json());
  }

  useEffect(() => { load().catch(() => setData(null)); }, []);

  async function taskStatus(id: string, status: string) {
    setBusy(id);
    try {
      await fetch(API + "/tasks/" + id + "/status", {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({status})
      });
      await load();
    } finally {
      setBusy(null);
    }
  }

  const d = data || {
    businesses:0, opportunities:0, proposals:0, clients:0, projects:0,
    open_tasks:0, pipeline_value:0, won_revenue:0,
    opportunities_queue:[], active_projects:[], tasks:[]
  };

  return (
    <main style={{padding:32,maxWidth:1200,margin:"0 auto",fontFamily:"system-ui"}}>
      <header style={{display:"flex",justifyContent:"space-between",alignItems:"center",gap:16}}>
        <div>
          <h1 style={{marginBottom:4}}>Luma</h1>
          <p style={{marginTop:0,color:"#666"}}>Business operating system: discover → research → qualify → sell → deliver → measure.</p>
        </div>
        <button onClick={() => load()} style={{padding:"10px 14px",borderRadius:8,border:"1px solid #ccc",background:"#fff",cursor:"pointer"}}>Refresh</button>
      </header>

      <section style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(150px,1fr))",gap:12,marginTop:24}}>
        {[
          ["Pipeline", money(d.pipeline_value)],
          ["Won revenue", money(d.won_revenue)],
          ["Opportunities", d.opportunities],
          ["Proposals", d.proposals],
          ["Clients", d.clients],
          ["Projects", d.projects],
          ["Open tasks", d.open_tasks],
          ["Prospects", d.businesses],
        ].map(([label,value]) =>
          <div key={String(label)} style={{border:"1px solid #ddd",borderRadius:12,padding:18}}>
            <div style={{fontSize:12,textTransform:"uppercase",color:"#777"}}>{label}</div>
            <div style={{fontSize:26,fontWeight:700,marginTop:6}}>{value}</div>
          </div>
        )}
      </section>

      <section style={{display:"grid",gridTemplateColumns:"minmax(0,1.35fr) minmax(0,1fr)",gap:20,marginTop:28}}>
        <div style={{border:"1px solid #ddd",borderRadius:12,padding:20}}>
          <h2 style={{marginTop:0}}>Opportunity queue</h2>
          {d.opportunities_queue.length === 0 ? <p style={{color:"#777"}}>No open opportunities yet.</p> :
            d.opportunities_queue.map((o) =>
              <div key={o.id} style={{padding:"14px 0",borderTop:"1px solid #eee"}}>
                <div style={{display:"flex",justifyContent:"space-between",gap:12}}>
                  <strong>{o.business_name}</strong><span>Score {o.score ?? "—"}</span>
                </div>
                <div style={{marginTop:4}}>{o.title}</div>
                <div style={{fontSize:13,color:"#666",marginTop:5}}>
                  {o.service_name || "Unassigned"} · {money(o.estimated_value_min)}–{money(o.estimated_value_max)}
                </div>
                <div style={{fontSize:13,marginTop:7}}>Next: {o.next_action || "Review"}</div>
              </div>
            )}
        </div>

        <div style={{border:"1px solid #ddd",borderRadius:12,padding:20}}>
          <h2 style={{marginTop:0}}>Active projects</h2>
          {d.active_projects.length === 0 ? <p style={{color:"#777"}}>No active projects yet.</p> :
            d.active_projects.map((p) =>
              <div key={p.id} style={{padding:"14px 0",borderTop:"1px solid #eee"}}>
                <strong>{p.business_name}</strong>
                <div>{p.name}</div>
                <div style={{fontSize:13,color:"#666"}}>{p.status} · {money(p.agreed_price)}</div>
              </div>
            )}
        </div>
      </section>

      <section style={{border:"1px solid #ddd",borderRadius:12,padding:20,marginTop:20}}>
        <h2 style={{marginTop:0}}>Delivery tasks</h2>
        {d.tasks.length === 0 ? <p style={{color:"#777"}}>No open delivery tasks.</p> :
          d.tasks.map((t) =>
            <div key={t.id} style={{display:"grid",gridTemplateColumns:"1fr auto",gap:12,padding:"14px 0",borderTop:"1px solid #eee"}}>
              <div>
                <strong>{t.title}</strong>
                <div style={{fontSize:13,color:"#666"}}>{t.business_name} · {t.project_name} · {t.priority}</div>
                {t.description && <div style={{fontSize:13,marginTop:4}}>{t.description}</div>}
              </div>
              <select disabled={busy === t.id} value={t.status} onChange={e => taskStatus(t.id,e.target.value)}>
                <option value="todo">To do</option>
                <option value="in_progress">In progress</option>
                <option value="blocked">Blocked</option>
                <option value="done">Done</option>
              </select>
            </div>
          )}
      </section>
    </main>
  );
}
