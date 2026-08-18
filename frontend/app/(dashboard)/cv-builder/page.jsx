"use client";

import { useState } from "react";
import { api, getToken } from "@/lib/api";
import { useAsync, Spinner, ErrorNote, EmptyState, Badge } from "@/components/ui";

function download(url, name) {
  const token = getToken();
  fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    .then((r) => r.blob())
    .then((b) => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(b);
      a.download = name;
      a.click();
      URL.revokeObjectURL(a.href);
    })
    .catch(() => {});
}

export default function CvBuilderPage() {
  const versions = useAsync(() => api("/cv/versions"));
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);

  const open = async (v) => {
    setSelected(v);
    try {
      setDetail(await api(`/cv/versions/${v.id}`));
    } catch (e) {
      setDetail({ error: e.message });
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">CV Builder</h1>
        <p className="text-sm text-slate-500">
          Tailored, ATS-friendly CVs — every claim fact-checked against your master profile.
        </p>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="md:col-span-1 space-y-2">
          {versions.loading ? <Spinner /> : versions.error ? (
            <ErrorNote message={versions.error} />
          ) : versions.data?.length === 0 ? (
            <EmptyState text="No CVs yet — generate one from the Applications page." />
          ) : (
            versions.data.map((v) => (
              <button key={v.id} onClick={() => open(v)}
                className={`card w-full text-left p-3 text-sm cursor-pointer hover:border-brand-500 transition-colors ${
                  selected?.id === v.id ? "border-brand-500" : ""}`}>
                <div className="font-medium text-slate-900 truncate">{v.target_role || "CV"}</div>
                <div className="text-xs text-slate-500">{v.version_label} · {v.created_at?.slice(0, 10)}</div>
              </button>
            ))
          )}
        </div>

        <div className="md:col-span-2">
          {!selected ? (
            <EmptyState text="Select a CV version to preview it." />
          ) : !detail ? (
            <Spinner />
          ) : detail.error ? (
            <ErrorNote message={detail.error} />
          ) : (
            <div className="space-y-3">
              <div className="card p-4">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                  <div>
                    <h2 className="font-bold text-slate-900">{detail.target_role}</h2>
                    <div className="text-xs text-slate-500">{detail.version_label}</div>
                  </div>
                  <div className="flex gap-2">
                    <button className="btn-secondary" onClick={() => download(`/api/v1/cv/versions/${detail.id}/download-docx`, `cv_${detail.target_role}.docx`)}>Download .docx</button>
                    <button className="btn-secondary" onClick={() => download(`/api/v1/cv/versions/${detail.id}/download-pdf`, `cv_${detail.target_role}.pdf`)}>Download .pdf</button>
                  </div>
                </div>
                {Object.entries(detail.snapshot?.sections || {}).map(([h, lines]) =>
                  lines?.length ? (
                    <div key={h} className="mb-3">
                      <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100 pb-1 mb-1">{h}</h3>
                      {lines.map((l, i) => <p key={i} className="text-sm text-slate-700">{l}</p>)}
                    </div>
                  ) : null
                )}
              </div>
              <div className="card p-4">
                <h3 className="font-semibold text-slate-900 mb-2">Fact-check report</h3>
                <div className="flex flex-wrap gap-2 mb-2">
                  <Badge tone="green">{detail.fact_check.verified_claims} verified</Badge>
                  <Badge tone={detail.fact_check.removed_claims ? "red" : "green"}>{detail.fact_check.removed_claims} removed</Badge>
                  <Badge tone={detail.fact_check.prohibited_findings?.length ? "red" : "green"}>
                    {detail.fact_check.prohibited_findings?.length || 0} prohibited
                  </Badge>
                </div>
                {(detail.fact_check.report || []).filter((r) => !r.verified).slice(0, 5).map((r, i) => (
                  <p key={i} className="text-xs text-red-600">✗ {r.claim}</p>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
