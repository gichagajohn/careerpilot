"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAsync, Spinner, ErrorNote } from "@/components/ui";

function Toggle({ label, desc, value, onChange }) {
  return (
    <label className="flex items-center justify-between gap-4 py-2.5 cursor-pointer">
      <div>
        <div className="text-sm font-medium text-slate-800">{label}</div>
        {desc ? <div className="text-xs text-slate-500">{desc}</div> : null}
      </div>
      <button type="button" onClick={onChange}
        className={`relative w-11 h-6 rounded-full transition-colors ${value ? "bg-brand-600" : "bg-slate-300"}`}>
        <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all ${value ? "left-5.5 left-[22px]" : "left-0.5"}`} />
      </button>
    </label>
  );
}

export default function SettingsPage() {
  const prefs = useAsync(() => api("/notifications/preferences"));
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const toggle = async (key) => {
    setErr(""); setMsg("");
    try {
      await api("/notifications/preferences", {
        method: "PUT",
        body: { [key]: !prefs.data[key] },
      });
      setMsg("Preferences saved.");
      prefs.reload();
    } catch (e) {
      setErr(e.message);
    }
  };

  if (prefs.loading) return <Spinner />;
  if (prefs.error) return <ErrorNote message={prefs.error} />;
  const p = prefs.data;

  return (
    <div className="space-y-4 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
        <p className="text-sm text-slate-500">Notification channels and triggers (spec §13).</p>
      </div>
      {msg && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{msg}</div>}
      <ErrorNote message={err} />

      <div className="card p-5">
        <h2 className="font-semibold text-slate-900 mb-1">Channels</h2>
        <p className="text-xs text-slate-500 mb-2">Email/Telegram need credentials in backend/.env.</p>
        <div className="divide-y divide-slate-100">
          <Toggle label="In-app notifications" value={p.in_app} onChange={() => {}} desc="Always on — the dashboard bell." />
          <Toggle label="Email" value={p.email} onChange={() => toggle("email")} desc="Requires SMTP_* in .env" />
          <Toggle label="Telegram" value={p.telegram} onChange={() => toggle("telegram")} desc="Requires TELEGRAM_BOT_TOKEN + CHAT_ID" />
        </div>
      </div>

      <div className="card p-5">
        <h2 className="font-semibold text-slate-900 mb-1">Triggers</h2>
        <p className="text-xs text-slate-500 mb-2">Which events notify you.</p>
        <div className="divide-y divide-slate-100">
          <Toggle label="High-match job found" value={p.high_match_job} onChange={() => toggle("high_match_job")} />
          <Toggle label="High-eligibility scholarship" value={p.high_eligibility_scholarship} onChange={() => toggle("high_eligibility_scholarship")} />
          <Toggle label="Deadline approaching" value={p.deadline_approaching} onChange={() => toggle("deadline_approaching")} />
          <Toggle label="Application ready" value={p.application_ready} onChange={() => toggle("application_ready")} />
          <Toggle label="Interview scheduled" value={p.interview_scheduled} onChange={() => toggle("interview_scheduled")} />
          <Toggle label="Follow-up due" value={p.followup_due} onChange={() => toggle("followup_due")} />
          <Toggle label="Opportunity expired" value={p.expired} onChange={() => toggle("expired")} />
        </div>
      </div>
    </div>
  );
}
