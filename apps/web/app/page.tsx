"use client";

import { useEffect, useState } from "react";

type Dashboard = Record<string, number>;

export default function Home() {
  const [data, setData] = useState<Dashboard | null>(null);

  useEffect(() => {
    const url = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(url + "/dashboard").then(r => r.json()).then(setData).catch(() => setData(null));
  }, []);

  return (
    <main style={{padding:32,maxWidth:1100,margin:"0 auto"}}>
      <h1>Jarvis</h1>
      <p>Business operating system: discover → sell → deliver → measure.</p>
      <section style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:16,marginTop:32}}>
        {Object.entries(data || {businesses:0,opportunities:0,proposals:0,clients:0,projects:0}).map(([k,v]) =>
          <div key={k} style={{border:"1px solid #ddd",borderRadius:12,padding:20}}>
            <div style={{fontSize:12,textTransform:"uppercase"}}>{k}</div>
            <div style={{fontSize:32,fontWeight:700}}>{v}</div>
          </div>
        )}
      </section>
    </main>
  );
}
