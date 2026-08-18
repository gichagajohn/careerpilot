"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import {
  Badge,
  EligibilityBadge,
  MatchScore,
  VerificationBadge,
  ErrorNote,
} from "@/components/ui";

export default function JobCard({ job, onApplied }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const md = job.match_details || {};

  const apply = async () => {
    setBusy(true);
    setError("");
    try {
      await api("/applications", {
        method: "POST",
        body: { job_id: job.id, status: "SHORTLISTED BY AGENT", match_score: job.match_score },
      });
      if (onApplied) onApplied(job.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const salary = job.salary_min || job.salary_max
    ? `${job.salary_currency || ""} ${job.salary_min || "?"}–${job.salary_max || "?"}`.trim()
    : "Salary not disclosed";

  return (
    <div className="card p-4 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-slate-900 leading-snug">{job.title}</h3>
          <div className="text-sm text-slate-500">{job.organization_name || "—"}</div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-2xl font-bold text-brand-600">
            <MatchScore score={job.match_score} />
          </div>
          <div className="text-[10px] uppercase text-slate-400">match</div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <span>📍 {job.location || "Remote/anywhere"}</span>
        <span>· {salary}</span>
        {job.deadline ? <span>· ⏰ {job.deadline}</span> : null}
      </div>

      <div className="flex flex-wrap gap-1.5">
        <VerificationBadge status={job.verification_status} />
        <EligibilityBadge label={job.eligibility} />
        {job.remote ? <Badge tone="blue">Remote</Badge> : null}
        {job.is_ai_training ? <Badge tone="purple">AI training</Badge> : null}
        {job.is_international ? <Badge tone="amber">International</Badge> : null}
      </div>

      {md.strengths?.length > 0 && (
        <ul className="text-xs text-emerald-700 space-y-0.5">
          {md.strengths.slice(0, 3).map((s, i) => (
            <li key={i}>✓ {s}</li>
          ))}
        </ul>
      )}
      {md.gaps?.length > 0 && (
        <ul className="text-xs text-amber-700 space-y-0.5">
          {md.gaps.slice(0, 3).map((g, i) => (
            <li key={i}>⚠ {g}</li>
          ))}
        </ul>
      )}
      {md.risks?.length > 0 && (
        <ul className="text-xs text-red-600 space-y-0.5">
          {md.risks.slice(0, 2).map((r, i) => (
            <li key={i}>! {r}</li>
          ))}
        </ul>
      )}

      <ErrorNote message={error} />
      <div className="mt-auto pt-2 flex items-center gap-2">
        <button className="btn-primary flex-1 justify-center" onClick={apply} disabled={busy}>
          {busy ? "Adding…" : "Add to applications"}
        </button>
        {job.application_url ? (
          <a className="btn-secondary" href={job.application_url} target="_blank" rel="noreferrer">
            View
          </a>
        ) : null}
      </div>
    </div>
  );
}
