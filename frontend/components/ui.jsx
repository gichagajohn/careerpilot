// Small shared UI components.

import { useCallback, useEffect, useState } from "react";

export function Spinner({ label = "Loading…" }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-500 py-8 justify-center">
      <svg className="animate-spin h-4 w-4 text-brand-500" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
      </svg>
      {label}
    </div>
  );
}

export function ErrorNote({ message }) {
  if (!message) return null;
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      {message}
    </div>
  );
}

export function EmptyState({ text }) {
  return <div className="py-12 text-center text-sm text-slate-400">{text}</div>;
}

export function StatCard({ label, value, accent = "text-slate-800", icon }) {
  return (
    <div className="card px-4 py-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{label}</div>
          <div className={`text-2xl font-bold mt-0.5 ${accent}`}>{value}</div>
        </div>
        {icon ? <div className="text-slate-300">{icon}</div> : null}
      </div>
    </div>
  );
}

export function Badge({ tone = "slate", children }) {
  const tones = {
    slate: "bg-slate-100 text-slate-600",
    green: "bg-emerald-100 text-emerald-700",
    amber: "bg-amber-100 text-amber-700",
    red: "bg-red-100 text-red-700",
    blue: "bg-blue-100 text-blue-700",
    purple: "bg-purple-100 text-purple-700",
  };
  return <span className={`badge ${tones[tone] || tones.slate}`}>{children}</span>;
}

export function VerificationBadge({ status }) {
  const map = {
    VERIFIED: ["green", "✓ Verified"],
    "LIKELY VERIFIED": ["blue", "Likely verified"],
    UNVERIFIED: ["amber", "Unverified"],
    SUSPICIOUS: ["red", "Suspicious"],
    EXPIRED: ["red", "Expired"],
  };
  const [tone, label] = map[status] || ["slate", status || "—"];
  return <Badge tone={tone}>{label}</Badge>;
}

export function EligibilityBadge({ label }) {
  const map = {
    ELIGIBLE: "green",
    "POSSIBLY ELIGIBLE": "amber",
    "NOT ELIGIBLE": "red",
  };
  return <Badge tone={map[label] || "slate"}>{label || "Not scored"}</Badge>;
}

export function MatchScore({ score }) {
  if (score === null || score === undefined) return <span className="text-slate-400">—</span>;
  const tone = score >= 80 ? "text-emerald-600" : score >= 50 ? "text-amber-600" : "text-slate-500";
  return <span className={`font-bold ${tone}`}>{Math.round(score)}</span>;
}

export function useAsync(loader, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    loader()
      .then((d) => {
        if (alive) {
          setData(d);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (alive) {
          setError(e.message || "Request failed");
          setLoading(false);
        }
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { data, error, loading, reload };
}
