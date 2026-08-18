"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAsync, Spinner, ErrorNote, Badge } from "@/components/ui";

export default function ProfilePage() {
  const profile = useAsync(() => api("/profile"));
  const [form, setForm] = useState(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  const start = () => {
    const p = profile.data || {};
    setForm({
      full_name: p.full_name || "", nationality: p.nationality || "", location: p.location || "",
      phone: p.phone || "", email: p.email || "", profession: p.profession || "",
      summary: p.summary || "", professional_registration: p.professional_registration || "",
    });
  };

  const save = async (e) => {
    e.preventDefault();
    setSaving(true); setErr(""); setMsg("");
    try {
      await api("/profile", { method: "PUT", body: form });
      setMsg("Profile saved — this is the single source of truth for all generated documents.");
      setForm(null);
      profile.reload();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setSaving(false);
    }
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  if (profile.loading) return <Spinner />;
  if (profile.error) return <ErrorNote message={profile.error} />;
  const p = profile.data;

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Master Profile</h1>
          <p className="text-sm text-slate-500">Only verified facts — never changed by generated documents.</p>
        </div>
        {!form && <button className="btn-primary" onClick={start}>Edit</button>}
      </div>
      {msg && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{msg}</div>}
      <ErrorNote message={err} />

      {form ? (
        <form onSubmit={save} className="card p-5 space-y-3">
          <div className="grid sm:grid-cols-2 gap-3">
            <div><label className="label">Full name</label><input className="input" value={form.full_name} onChange={set("full_name")} required /></div>
            <div><label className="label">Nationality</label><input className="input" value={form.nationality} onChange={set("nationality")} /></div>
            <div><label className="label">Location</label><input className="input" value={form.location} onChange={set("location")} /></div>
            <div><label className="label">Phone</label><input className="input" value={form.phone} onChange={set("phone")} /></div>
            <div><label className="label">Email</label><input className="input" type="email" value={form.email} onChange={set("email")} /></div>
            <div><label className="label">Profession</label><input className="input" value={form.profession} onChange={set("profession")} /></div>
          </div>
          <div><label className="label">Professional registration</label><input className="input" value={form.professional_registration} onChange={set("professional_registration")} /></div>
          <div><label className="label">Summary</label><textarea className="input" rows={3} value={form.summary} onChange={set("summary")} /></div>
          <div className="flex gap-2">
            <button className="btn-primary" disabled={saving}>{saving ? "Saving…" : "Save"}</button>
            <button type="button" className="btn-secondary" onClick={() => setForm(null)}>Cancel</button>
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
