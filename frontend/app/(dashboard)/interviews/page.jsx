"use client";

import { api } from "@/lib/api";
import { useAsync, Spinner, ErrorNote, EmptyState, Badge } from "@/components/ui";

export default function InterviewsPage() {
  const apps = useAsync(() => api("/applications?status_filter=INTERVIEW"));

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Interviews</h1>
        <p className="text-sm text-slate-500">Applications at the interview stage.</p>
      </div>

      {apps.loading ? <Spinner /> : apps.error ? (
        <ErrorNote message={apps.error} />
      ) : apps.data?.length === 0 ? (
        <EmptyState text="No interviews scheduled yet." />
      ) : (
        <div className="space-y-3">
          {apps.data.map((a) => {
            const target = a.job ? a.job.title : a.scholarship ? a.scholarship.name : "—";
            const org = a.job ? a.job.organization_name : a.scholarship ? a.scholarship.university : "";
            return (
              <div key={a.id} className="card p-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="font-semibold text-slate-900">{target}</div>
                  <div className="text-sm text-slate-500">{org}</div>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Badge tone="blue">{a.interview_date || "date TBC"}</Badge>
                  <span className="text-slate-400 text-xs">follow-up: {a.follow_up_date || "—"}</span>
                </div>
              </div>
            );
          })}
          <p className="text-xs text-slate-400">
            Interview question banks and mock interviews arrive in Phase 10.
          </p>
        </div>
      )}
    </div>
  );
}
