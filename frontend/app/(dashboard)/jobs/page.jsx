"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAsync, Spinner, ErrorNote, EmptyState } from "@/components/ui";
import JobCard from "@/components/JobCard";

export default function JobsPage() {
  const [q, setQ] = useState("");
  const [verification, setVerification] = useState("");
  const [minMatch, setMinMatch] = useState("");

  const jobs = useAsync(
    () =>
      api("/jobs", {
        params: { q: q || undefined, verification_status: verification || undefined, min_match: minMatch || undefined },
      }),
    [q, verification, minMatch]
  );

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Jobs</h1>
        <p className="text-sm text-slate-500">Discovered teaching &amp; AI-training opportunities.</p>
      </div>

      <div className="card p-3 grid gap-2 sm:grid-cols-4">
        <input className="input sm:col-span-2" placeholder="Search title / organisation…" value={q}
          onChange={(e) => setQ(e.target.value)} />
        <select className="input" value={verification} onChange={(e) => setVerification(e.target.value)}>
          <option value="">All verification</option>
          <option>VERIFIED</option>
          <option>LIKELY VERIFIED</option>
          <option>UNVERIFIED</option>
          <option>SUSPICIOUS</option>
          <option>EXPIRED</option>
        </select>
        <input className="input" type="number" placeholder="Min match (0-100)" value={minMatch}
          onChange={(e) => setMinMatch(e.target.value)} />
      </div>

      {jobs.loading ? <Spinner /> : jobs.error ? (
        <ErrorNote message={jobs.error} />
      ) : jobs.data?.length === 0 ? (
        <EmptyState text="No jobs found." />
      ) : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
          {jobs.data.map((j) => <JobCard key={j.id} job={j} onApplied={() => jobs.reload()} />)}
        </div>
      )}
    </div>
  );
}
