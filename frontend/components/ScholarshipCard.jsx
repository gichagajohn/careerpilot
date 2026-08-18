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

function Row({ k, v }) {
  return v ? (
    <div className="text-xs">
      <span className="font-semibold text-slate-500">{k}: </span>
      <span className="text-slate-700">{v}</span>
    </div>
  ) : null;
}

export default function ScholarshipCard({ scholarship, onAdded }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const md = scholarship.match_details || {};

  const add = async () => {
    setBusy(true);
    setError("");
    try {
      await api("/applications", {
        method: "POST",
        body: { scholarship_id: scholarship.id, status: "SHORTLISTED BY AGENT", match_score: scholarship.match_score },
      });
      if (onAdded) onAdded(scholarship.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const funding = (scholarship.funding_level || "").replace(/_/g, " ");
  const fundingTone =
    scholarship.funding_level === "FULLY FUNDED" ? "green"
    : ["PARTIAL", "TUITION-ONLY"].includes(scholarship.funding_level) ? "amber" : "slate";

  return (
    <div className="card p-4 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-slate-900 leading-snug">{scholarship.name}</h3>
          <div className="text-sm text-slate-500">{scholarship.university || "—"}</div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-2xl font-bold text-brand-600">
            <MatchScore score={scholarship.match_score} />
          </div>
          <div className="text-[10px] uppercase text-slate-400">match</div>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Badge tone={fundingTone}>{funding || "Funding n/a"}</Badge>
        <VerificationBadge status={scholarship.verification_status} />
        <EligibilityBadge label={scholarship.eligibility_label} />
        {scholarship.open_to_kenyans ? <Badge tone="blue">Kenya</Badge> : null}
        {scholarship.open_to_africans ? <Badge tone="blue">Africa</Badge> : null}
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
        <Row k="Country" v={scholarship.country} />
        <Row k="Programme" v={scholarship.programme} />
        <Row k="Tuition" v={scholarship.tuition_coverage} />
        <Row k="Stipend" v={scholarship.living_allowance} />
        <Row k="Deadline" v={scholarship.deadline} />
        <Row k="Classification" v={scholarship.required_classification} />
      </div>

      {md.strengths?.length > 0 && (
        <ul className="text-xs text-emerald-700 space-y-0.5">
          {md.strengths.slice(0, 3).map((s, i) => (
            <li key={i}>✓ {s}</li>
          ))}
        </ul>
      )}

      <ErrorNote message={error} />
      <div className="mt-auto pt-2 flex items-center gap-2">
        <button className="btn-primary flex-1 justify-center" onClick={add} disabled={busy}>
          {busy ? "Adding…" : "Add to applications"}
        </button>
        {scholarship.application_url ? (
          <a className="btn-secondary" href={scholarship.application_url} target="_blank" rel="noreferrer">
            Apply site
          </a>
        ) : null}
      </div>
    </div>
  );
}
