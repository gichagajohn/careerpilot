"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAsync, Spinner, ErrorNote, Badge } from "@/components/ui";

const EMPTY = {
  full_name: "", nationality: "", location: "", phone: "",
  email: "", profession: "", summary: "", professional_registration: "",
};

// A profile the API could not return (older backend returning 404) is treated
// as "not created yet" — the setup form is shown instead of a dead-end error.
const isMissingProfile = (message) =>
  typeof message === "string" && /profile not found/i.test(message);

export default function ProfilePage() {
  const profile = useAsync(() => api("/profile"));
  const [form, setForm] = useState(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  const start = () => {
    const p = profile.data || {};
    setForm({ ...EMPTY, ...Object.fromEntries(
      Object.keys(EMPTY).map((k) => [k, p[k] || ""])
    ) });
  };

  const save = async (e) => {
    e.preventDefault();
    setSaving(true); setErr(""); setMsg("");
    try {
      await api("/profile", { method: "PUT", body: form || setupForm });
      setMsg("Profile saved — this is the single source of truth for all generated documents.");
      setForm(null);
      profile.reload();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setSaving(false);
    }
  };

  const set = (k) => (e) => setForm({ ...(form || setupForm), [k]: e.target.value });

  if (profile.loading) return <Spinner />;
  // A missing profile is a first-run state, not an error: fall through to the
  // setup form so the user can create it. Real failures still surface.
  if (profile.error && !isMissingProfile(profile.error))
    return <ErrorNote message={profile.error} />;

  const p = profile.data;
  const needsSetup = !p || p.profile_complete === false;
  const setupForm = form || (needsSetup ? { ...EMPTY, ...(p ? Object.fromEntries(
    Object.keys(EMPTY).map((k) => [k, p[k] || ""])
  ) : {}) } : null);

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Master Profile</h1>
          <p className="text-sm text-slate-500">Only verified facts — never changed by generated documents.</p>
        </div>
        {!setupForm && <button className="btn-primary" onClick={start}>Edit</button>}
      </div>
      {msg && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{msg}</div>}
      {needsSetup && !msg && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Welcome! Your master profile is empty. Fill in the details below to finish setting it up —
          everything CareerPilot generates is based only on these verified facts.
        </div>
      )}
      <ErrorNote message={err} />

      {setupForm ? (
        <form onSubmit={save} className="card p-5 space-y-3">
          <div className="grid sm:grid-cols-2 gap-3">
            <div><label className="label">Full name</label><input className="input" value={setupForm.full_name} onChange={set("full_name")} required /></div>
            <div><label className="label">Nationality</label><input className="input" value={setupForm.nationality} onChange={set("nationality")} /></div>
            <div><label className="label">Location</label><input className="input" value={setupForm.location} onChange={set("location")} /></div>
            <div><label className="label">Phone</label><input className="input" value={setupForm.phone} onChange={set("phone")} /></div>
            <div><label className="label">Email</label><input className="input" type="email" value={setupForm.email} onChange={set("email")} /></div>
            <div><label className="label">Profession</label><input className="input" value={setupForm.profession} onChange={set("profession")} /></div>
          </div>
          <div><label className="label">Professional registration</label><input className="input" value={setupForm.professional_registration} onChange={set("professional_registration")} /></div>
          <div><label className="label">Summary</label><textarea className="input" rows={3} value={setupForm.summary} onChange={set("summary")} /></div>
          <div className="flex gap-2">
            <button className="btn-primary" disabled={saving}>{saving ? "Saving…" : needsSetup ? "Create profile" : "Save"}</button>
            {!needsSetup && (
              <button type="button" className="btn-secondary" onClick={() => setForm(null)}>Cancel</button>
            )}
          </div>
        </form>
      ) : (
        <div className="card p-5 space-y-4">
          <div className="grid sm:grid-cols-2 gap-3 text-sm">
            <div><div className="text-xs text-slate-400 uppercase">Name</div><div className="font-medium">{p.full_name}</div></div>
            <div><div className="text-xs text-slate-400 uppercase">Nationality</div><div>{p.nationality}</div></div>
            <div><div className="text-xs text-slate-400 uppercase">Location</div><div>{p.location}</div></div>
            <div><div className="text-xs text-slate-400 uppercase">Phone</div><div>{p.phone}</div></div>
            <div><div className="text-xs text-slate-400 uppercase">Email</div><div>{p.email}</div></div>
            <div><div className="text-xs text-slate-400 uppercase">Profession</div><div>{p.profession}</div></div>
            <div className="sm:col-span-2"><div className="text-xs text-slate-400 uppercase">Registration</div><div>{p.professional_registration}</div></div>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <div className="card p-3">
              <div className="text-xs font-semibold text-slate-400 uppercase mb-1">Education</div>
              {p.education?.map((e, i) => <p key={i} className="text-sm">{e.degree} — {e.institution} <Badge>{e.classification}</Badge></p>)}
            </div>
            <div className="card p-3">
              <div className="text-xs font-semibold text-slate-400 uppercase mb-1">Experience</div>
              {p.experience?.map((e, i) => <p key={i} className="text-sm">{e.role} — {e.organization}</p>)}
            </div>
            <div className="card p-3 sm:col-span-2">
              <div className="text-xs font-semibold text-slate-400 uppercase mb-1">Skills ({p.skills?.length})</div>
              <div className="flex flex-wrap gap-1.5">
                {p.skills?.map((s) => <Badge key={s.id} tone="blue">{s.name}</Badge>)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
