"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAsync, Spinner, ErrorNote, EmptyState, Badge } from "@/components/ui";

const STATUSES = [
  "DISCOVERED", "VERIFIED", "SHORTLISTED BY AGENT", "READY FOR REVIEW", "APPROVED",
  "APPLIED", "INTERVIEW", "OFFER", "REJECTED", "WITHDRAWN", "EXPIRED",
];

function tone(status) {
  const map = {
    INTERVIEW: "blue", OFFER: "green", APPLIED: "purple", APPROVED: "green",
    REJECTED: "red", WITHDRAWN: "slate", EXPIRED: "red",
  };
  return map[status] || "slate";
}

export default function ApplicationsPage() {
  const apps = useAsync(() => api("/applications"));
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const setStatus = async (id, status) => {
    setErr("");
    setMsg("");
    try {
      await api(`/applications/${id}`, { method: "PATCH", body: { status } });
      setMsg(`Application ${id} → ${status}`);
      apps.reload();
    } catch (e) {
      setErr(e.message);
    }
  };

  const genCv = async (id) => {
    setErr(""); setMsg("");
    try {
      await api(`/cv/applications/${id}/generate`, { method: "POST" });
      setMsg(`CV generated for application ${id} — see CV Builder.`);
    } catch (e) { setErr(e.message); }
  };

  const genLetter = async (id) => {
    setErr(""); setMsg("");
    try {
      await api(`/cover-letters/applications/${id}/generate`, { method: "POST" });
      setMsg(`Cover letter generated for application ${id} — see Cover Letters.`);
    } catch (e) { setErr(e.message); }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Applications</h1>
        <p className="text-sm text-slate-500">Full lifecycle tracker (spec §11).</p>
      </div>
      {msg && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{msg}</div>}
      <ErrorNote message={err} />

      {apps.loading ? <Spinner /> : apps.error ? (
        <ErrorNote message={apps.error} />
      ) : apps.data?.length === 0 ? (
        <EmptyState text="No applications yet — add opportunities from Jobs or Scholarships." />
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[900px]">
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                <th className="th">Target</th>
                <th className="th">Match</th>
                <th className="th">Status</th>
                <th className="th">Interview</th>
                <th className="th">Follow-up</th>
                <th className="th">Documents</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {apps.data.map((a) => {
                const target = a.job ? a.job.title : a.scholarship ? a.scholarship.name : "—";
                const org = a.job ? a.job.organization_name : a.scholarship ? a.scholarship.university : "";
                return (
                  <tr key={a.id}>
                    <td className="td">
                      <div className="font-medium text-slate-900">{target}</div>
                      <div className="text-xs text-slate-500">{org}</div>
                    </td>
                    <td className="td"><span className="font-bold text-brand-600">{a.match_score != null ? Math.round(a.match_score) : "—"}</span></td>
                    <td className="td">
                      <div className="flex items-center gap-2">
                        <Badge tone={tone(a.status)}>{a.status}</Badge>
                        <select className="input w-40" value={a.status}
                          onChange={(e) => setStatus(a.id, e.target.value)}>
                          {STATUSES.map((s) => <option key={s}>{s}</option>)}
                        </select>
                      </div>
                    </td>
                    <td className="td text-slate-600">{a.interview_date || "—"}</td>
                    <td className="td text-slate-600">{a.follow_up_date || "—"}</td>
                    <td className="td">
                      <div className="flex flex-wrap gap-1.5">
                        <button className="btn-secondary text-xs px-2 py-1" onClick={() => genCv(a.id)}>CV</button>
                        <button className="btn-secondary text-xs px-2 py-1" onClick={() => genLetter(a.id)}>Letter</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
