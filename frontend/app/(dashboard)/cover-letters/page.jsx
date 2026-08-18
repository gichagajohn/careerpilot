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

export default function CoverLettersPage() {
  const letters = useAsync(() => api("/cover-letters"));
  const [selected, setSelected] = useState(null);
  const [content, setContent] = useState(null);

  const open = async (l) => {
    setSelected(l);
    setContent(l.content);
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Cover Letters</h1>
        <p className="text-sm text-slate-500">Role-specific letters, fact-checked against your profile.</p>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="md:col-span-1 space-y-2">
          {letters.loading ? <Spinner /> : letters.error ? (
            <ErrorNote message={letters.error} />
          ) : letters.data?.length === 0 ? (
            <EmptyState text="No letters yet — generate one from the Applications page." />
          ) : (
            letters.data.map((l) => (
              <button key={l.id} onClick={() => open(l)}
                className={`card w-full text-left p-3 text-sm cursor-pointer hover:border-brand-500 transition-colors ${
                  selected?.id === l.id ? "border-brand-500" : ""}`}>
                <div className="font-medium text-slate-900">Application #{l.application_id}</div>
                <div className="text-xs text-slate-500">{l.created_at?.slice(0, 10)}</div>
              </button>
            ))
          )}
        </div>

        <div className="md:col-span-2">
          {!selected ? (
            <EmptyState text="Select a letter to read it." />
          ) : (
            <div className="card p-5 space-y-3">
              <div className="flex justify-end gap-2">
                <button className="btn-secondary" onClick={() => download(`/api/v1/cover-letters/${selected.id}/download-docx`, "cover_letter.docx")}>.docx</button>
                <button className="btn-secondary" onClick={() => download(`/api/v1/cover-letters/${selected.id}/download-pdf`, "cover_letter.pdf")}>.pdf</button>
              </div>
              <div className="whitespace-pre-wrap text-sm text-slate-700 leading-relaxed">{content}</div>
              {selected.fact_check_report ? <Badge tone="green">Fact-checked</Badge> : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
