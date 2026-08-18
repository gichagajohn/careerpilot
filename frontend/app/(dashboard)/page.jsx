"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useAsync, StatCard, Spinner, ErrorNote, EmptyState, Badge } from "@/components/ui";
import JobCard from "@/components/JobCard";
import ScholarshipCard from "@/components/ScholarshipCard";

export default function DashboardPage() {
  const summary = useAsync(() => api("/dashboard/summary"));
  const recs = useAsync(() => api("/recommendations?limit=5"));

  if (summary.loading || recs.loading) return <Spinner />;
  const err = summary.error || recs.error;
  if (err) return <ErrorNote message={err} />;
  const s = summary.data || {};
  const jobs = (recs.data?.jobs || []).filter((j) => j.verification_status !== "EXPIRED");
  const scholarships = (recs.data?.scholarships || []).filter(
    (x) => x.verification_status !== "EXPIRED"
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-sm text-slate-500">Your opportunities, ranked by match &amp; priority.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Total opportunities" value={s.total_opportunities ?? 0} accent="text-brand-600" />
        <StatCard label="New (7d)" value={s.new_opportunities ?? 0} accent="text-slate-800" />
        <StatCard label="High match (≥80)" value={s.high_match_opportunities ?? 0} accent="text-emerald-600" />
        <StatCard label="Applications" value={s.applications_total ?? 0} accent="text-slate-800" />
        <StatCard label="Interviews" value={s.applications_interviews ?? 0} accent="text-blue-600" />
        <StatCard label="Offers" value={s.applications_offers ?? 0} accent="text-emerald-600" />
        <StatCard label="Scholarships" value={s.scholarships_total ?? 0} accent="text-purple-600" />
        <StatCard label="Deadlines (14d)" value={(s.upcoming_deadlines || []).length} accent="text-amber-600" />
      </div>

      {s.upcoming_deadlines?.length > 0 && (
        <div className="card p-4">
          <h2 className="font-semibold text-slate-900 mb-2">Upcoming deadlines</h2>
          <ul className="space-y-1 text-sm">
            {s.upcoming_deadlines.map((d, i) => (
              <li key={i} className="flex items-center gap-2">
                <Badge tone="amber">⏰ {d.due_date}</Badge>
                <span className="text-slate-700">{d.title}</span>
                <span className="text-slate-400 text-xs">{d.organization}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-bold text-slate-900">High-match jobs</h2>
          <Link href="/jobs" className="text-sm text-brand-600 hover:underline">View all →</Link>
        </div>
        {jobs.length === 0 ? (
          <EmptyState text="No jobs ranked yet — run the matcher or discover opportunities." />
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
            {jobs.map((j) => <JobCard key={j.id} job={j} />)}
          </div>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-bold text-slate-900">Scholarships</h2>
          <Link href="/scholarships" className="text-sm text-brand-600 hover:underline">View all →</Link>
        </div>
        {scholarships.length === 0 ? (
          <EmptyState text="No scholarships ranked yet." />
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
            {scholarships.map((x) => <ScholarshipCard key={x.id} scholarship={x} />)}
          </div>
        )}
      </div>
    </div>
  );
}
