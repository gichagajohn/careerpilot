"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAsync, Spinner, ErrorNote, EmptyState } from "@/components/ui";
import ScholarshipCard from "@/components/ScholarshipCard";

export default function ScholarshipsPage() {
  const [q, setQ] = useState("");
  const [funding, setFunding] = useState("");

  const list = useAsync(
    () => api("/scholarships", { params: { q: q || undefined, funding_level: funding || undefined } }),
    [q, funding]
  );

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Scholarships</h1>
        <p className="text-sm text-slate-500">Master's opportunities — funding confirmed only with official evidence.</p>
      </div>

      <div className="card p-3 grid gap-2 sm:grid-cols-3">
        <input className="input sm:col-span-2" placeholder="Search name / university / programme…" value={q}
          onChange={(e) => setQ(e.target.value)} />
        <select className="input" value={funding} onChange={(e) => setFunding(e.target.value)}>
          <option value="">All funding</option>
          <option>FULLY FUNDED</option>
          <option>TUITION-FREE</option>
          <option>TUITION-ONLY</option>
          <option>PARTIAL</option>
          <option>UNSPECIFIED</option>
        </select>
      </div>

      {list.loading ? <Spinner /> : list.error ? (
        <ErrorNote message={list.error} />
      ) : list.data?.length === 0 ? (
        <EmptyState text="No scholarships found." />
      ) : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
          {list.data.map((s) => <ScholarshipCard key={s.id} scholarship={s} onAdded={() => list.reload()} />)}
        </div>
      )}
    </div>
  );
}
