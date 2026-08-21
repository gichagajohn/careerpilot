"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAsync, Spinner, ErrorNote, Badge } from "@/components/ui";

// Applications prepared by the agent, waiting for the user to read and send.
// Nothing here submits on your behalf: "Open application form" takes you to the
// employer's own page, and you mark it applied once you have actually sent it.

export default function ReviewPage() {
  const queue = useAsync(() => api("/applications/review-queue"));
  const [busy, setBusy] = useState(false);
  const [count, setCount] = useState(5);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [marking, setMarking] = useState(null);
  const [opened, setOpened] = useState([]);

  const prepare = async () => {
    setBusy(true); setErr(""); setMsg("");
    try {
      const r = await api("/applications/prepare-batch", { method: "POST", params: { limit: count } });
      if (r.candidates_found === 0) {
        setMsg("No new opportunities scored high enough yet. Run the discovery agents, or lower the match threshold in Settings.");
      } else {
        setMsg(`Prepared ${r.prepared} of ${r.candidates_found} — CV and cover letter generated for each.`
               + (r.incomplete ? ` ${r.incomplete} need attention (see the notes below).` : ""));
      }
      queue.reload();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  };

  const markApplied = async (id) => {
    setMarking(id); setErr("");
    try {
      await api(`/applications/${id}`, { method: "PATCH", body: { status: "APPLIED" } });
      queue.reload();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setMarking(null);
    }
  };

  if (queue.loading) return <Spinner />;
  if (queue.error) return <ErrorNote message={queue.error} />;
  const items = queue.data || [];

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Review &amp; submit</h1>
          <p className="text-sm text-slate-500">
            Applications the agent has prepared. Read each one, then submit it yourself.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-500">Prepare</label>
          <select className="input w-16 py-1" value={count} onChange={(e) => setCount(Number(e.target.value))}>
            {[1, 3, 5, 10, 20].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          <button className="btn-primary whitespace-nowrap" onClick={prepare} disabled={busy}>
            {busy ? "Preparing…" : "Prepare applications"}
          </button>
        </div>
      </div>

      {msg && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{msg}</div>}
      <ErrorNote message={err} />

      <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
        CareerPilot never submits an application for you. It writes a fact-checked CV and
        cover letter from your master profile; you open the employer&apos;s form, check the
        details and send it.
      </div>

      {items.length === 0 ? (
        <div className="card p-8 text-center text-sm text-slate-500">
          Nothing queued yet. Click <span className="font-medium">Prepare applications</span> to
          build a batch from your highest-scoring opportunities.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((it) => (
            <div key={it.application_id} className="card p-4 space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-semibold text-slate-900">{it.title || "Untitled role"}</div>
                  <div className="text-sm text-slate-500">
                    {it.organization || "—"}{it.location ? ` · ${it.location}` : ""}
                  </div>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {it.match_score != null && (
                    <Badge tone={it.match_score >= 80 ? "green" : "blue"}>
                      {Math.round(it.match_score)}% match
                    </Badge>
                  )}
                  {it.eligibility && <Badge>{it.eligibility}</Badge>}
                  {it.deadline && <Badge tone="amber">Due {it.deadline}</Badge>}
                </div>
              </div>

              {(it.strengths?.length > 0 || it.gaps?.length > 0) && (
                <div className="grid sm:grid-cols-2 gap-2 text-xs">
                  {it.strengths?.length > 0 && (
                    <div>
                      <div className="font-semibold uppercase text-slate-400 mb-0.5">Strengths</div>
                      <ul className="list-disc list-inside text-slate-600 space-y-0.5">
                        {it.strengths.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                    </div>
                  )}
                  {it.gaps?.length > 0 && (
                    <div>
                      <div className="font-semibold uppercase text-slate-400 mb-0.5">Gaps to address</div>
                      <ul className="list-disc list-inside text-slate-600 space-y-0.5">
                        {it.gaps.map((g, i) => <li key={i}>{g}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {it.problems?.length > 0 && (
                <div className="rounded border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs text-amber-800">
                  {it.problems.join(" · ")}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-slate-100">
                <span className="text-xs font-semibold uppercase text-slate-400 mr-1">Documents</span>
                {it.cv_pdf
                  ? <><a className="btn-secondary text-xs py-1" href={it.cv_pdf} target="_blank" rel="noreferrer">CV (PDF)</a>
                      <a className="btn-secondary text-xs py-1" href={it.cv_docx} target="_blank" rel="noreferrer">CV (DOCX)</a></>
                  : <span className="text-xs text-slate-400">CV not generated</span>}
                {it.letter_pdf
                  ? <><a className="btn-secondary text-xs py-1" href={it.letter_pdf} target="_blank" rel="noreferrer">Letter (PDF)</a>
                      <a className="btn-secondary text-xs py-1" href={it.letter_docx} target="_blank" rel="noreferrer">Letter (DOCX)</a></>
                  : <span className="text-xs text-slate-400">Letter not generated</span>}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {it.apply_url ? (
                  <a
                    className="btn-primary" href={it.apply_url} target="_blank" rel="noreferrer"
                    onClick={() => setOpened((o) => [...new Set([...o, it.application_id])])}
                  >
                    Open application form ↗
                  </a>
                ) : (
                  <span className="text-xs text-slate-400">No application link on this listing</span>
                )}
                <button
                  className="btn-secondary"
                  disabled={marking === it.application_id}
                  onClick={() => markApplied(it.application_id)}
                >
                  {marking === it.application_id ? "Saving…" : "I've submitted this"}
                </button>
                {opened.includes(it.application_id) && (
                  <span className="text-xs text-slate-500">
                    Form opened — mark it once you have actually sent it.
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
