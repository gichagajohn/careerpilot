"use client";

import { useRef, useState } from "react";
import { api, upload } from "@/lib/api";
import { useAsync, Spinner, ErrorNote, Badge } from "@/components/ui";

const EMPTY = {
  full_name: "", nationality: "", location: "", phone: "",
  email: "", profession: "", summary: "", professional_registration: "",
};

// A profile the API could not return (older backend returning 404) is treated
// as "not created yet" — the setup form is shown instead of a dead-end error.
const isMissingProfile = (message) =>
  typeof message === "string" && /profile not found/i.test(message);

const pick = (source) =>
  Object.fromEntries(Object.keys(EMPTY).map((k) => [k, (source && source[k]) || ""]));

const CV_ACCEPT = ".pdf,.docx,.txt,.md";

export default function ProfilePage() {
  const profile = useAsync(() => api("/profile"));
  const [form, setForm] = useState(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  // ── CV import state ──────────────────────────────────────────
  const fileRef = useRef(null);
  const errRef = useRef(null);
  const [importing, setImporting] = useState(false);
  const [cvFields, setCvFields] = useState([]);      // field names filled from the CV
  const [cvNotice, setCvNotice] = useState("");
  const [cvWarnings, setCvWarnings] = useState([]);
  const [extras, setExtras] = useState(null);        // { education, experience, skills }
  const [chosen, setChosen] = useState({ education: [], experience: [], skills: [] });

  const start = () => setForm(pick(profile.data || {}));

  const importCv = async (file) => {
    if (!file) return;
    setImporting(true); setErr(""); setMsg(""); setCvNotice(""); setCvWarnings([]);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await upload("/profile/import-cv", fd);

      const found = res.filled_fields || [];
      const base = form || setupForm || { ...EMPTY };
      const merged = { ...base };
      for (const k of Object.keys(EMPTY)) {
        const v = res.profile?.[k];
        if (v) merged[k] = v;
      }
      setForm(merged);
      setCvFields(found);

      const ex = {
        education: res.education || [],
        experience: res.experience || [],
        skills: res.skills || [],
      };
      setExtras(ex);
      setChosen({
        education: ex.education.map((_, i) => i),
        experience: ex.experience.map((_, i) => i),
        skills: ex.skills.map((_, i) => i),
      });
      setCvWarnings(res.warnings || []);

      const counts = [
        found.length && `${found.length} field${found.length === 1 ? "" : "s"}`,
        ex.education.length && `${ex.education.length} education`,
        ex.experience.length && `${ex.experience.length} experience`,
        ex.skills.length && `${ex.skills.length} skills`,
      ].filter(Boolean);
      setCvNotice(
        counts.length
          ? `Read ${counts.join(", ")} from your CV${res.parser === "fallback" ? " (offline parser)" : ""}. Please check everything before saving.`
          : "We could not read any details from this CV."
      );
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const toggle = (kind, i) =>
    setChosen((c) => ({
      ...c,
      [kind]: c[kind].includes(i) ? c[kind].filter((x) => x !== i) : [...c[kind], i],
    }));

  const save = async (e) => {
    e.preventDefault();
    setSaving(true); setErr(""); setMsg("");
    try {
      await api("/profile", { method: "PUT", body: form || setupForm });

      // Then add the CV entries the user kept ticked. Failures here must not
      // lose the profile that was just saved, so they are collected and shown.
      const problems = [];
      if (extras) {
        for (const i of chosen.education) {
          try { await api("/profile/education", { method: "POST", body: extras.education[i] }); }
          catch (ex) { problems.push(`Education "${extras.education[i].degree || i}": ${ex.message}`); }
        }
        for (const i of chosen.experience) {
          try { await api("/profile/experience", { method: "POST", body: extras.experience[i] }); }
          catch (ex) { problems.push(`Experience "${extras.experience[i].role || i}": ${ex.message}`); }
        }
        for (const i of chosen.skills) {
          try { await api("/profile/skills", { method: "POST", body: extras.skills[i] }); }
          catch (ex) {
            // A duplicate skill is not a real failure — it is already there.
            if (!/already exists/i.test(ex.message)) {
              problems.push(`Skill "${extras.skills[i].name}": ${ex.message}`);
            }
          }
        }
      }

      setMsg("Profile saved — this is the single source of truth for all generated documents.");
      if (problems.length) setErr(`Saved, but some entries were skipped: ${problems.join("; ")}`);
      setForm(null);
      setExtras(null);
      setCvFields([]);
      setCvNotice("");
      setCvWarnings([]);
      profile.reload();
    } catch (ex) {
      setErr(ex.message || "Could not save your profile. Please try again.");
      // The form is long: bring the message to the user instead of leaving it
      // off-screen at the top of the page.
      requestAnimationFrame(() =>
        errRef.current?.scrollIntoView({ behavior: "smooth", block: "center" })
      );
    } finally {
      setSaving(false);
    }
  };

  const set = (k) => (e) => {
    setForm({ ...(form || setupForm), [k]: e.target.value });
    setCvFields((f) => f.filter((x) => x !== k)); // user edited it — no longer "from CV"
  };

  // Amber ring marks a value that came from the CV and still needs checking.
  const inputClass = (k) =>
    cvFields.includes(k) ? "input ring-2 ring-amber-300 bg-amber-50/40" : "input";
  const FromCv = ({ k }) =>
    cvFields.includes(k) ? <span className="ml-1.5 text-[10px] font-medium text-amber-600">from CV</span> : null;

  if (profile.loading) return <Spinner />;
  // A missing profile is a first-run state, not an error: fall through to the
  // setup form so the user can create it. Real failures still surface.
  if (profile.error && !isMissingProfile(profile.error))
    return <ErrorNote message={profile.error} />;

  const p = profile.data;
  const needsSetup = !p || p.profile_complete === false;
  const setupForm = form || (needsSetup ? { ...EMPTY, ...pick(p) } : null);

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
          {/* ── Import from CV ───────────────────────────── */}
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-sm font-semibold text-slate-700">Start from your CV</div>
                <div className="text-xs text-slate-500">
                  Upload a PDF, DOCX or TXT and we will fill in what we can find. Nothing is
                  saved until you review it and click {needsSetup ? '"Create profile"' : '"Save"'}.
                </div>
              </div>
              <input
                ref={fileRef} type="file" accept={CV_ACCEPT} className="hidden"
                onChange={(e) => importCv(e.target.files?.[0])}
              />
              <button
                type="button" className="btn-secondary whitespace-nowrap" disabled={importing}
                onClick={() => fileRef.current?.click()}
              >
                {importing ? "Reading CV…" : "Upload CV"}
              </button>
            </div>
            {cvNotice && (
              <div className="mt-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                {cvNotice}
              </div>
            )}
            {cvWarnings.map((w, i) => (
              <div key={i} className="mt-2 rounded border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">{w}</div>
            ))}
          </div>

          <div className="grid sm:grid-cols-2 gap-3">
            <div><label className="label">Full name<FromCv k="full_name" /></label><input className={inputClass("full_name")} value={setupForm.full_name} onChange={set("full_name")} required /></div>
            <div><label className="label">Nationality<FromCv k="nationality" /></label><input className={inputClass("nationality")} value={setupForm.nationality} onChange={set("nationality")} /></div>
            <div><label className="label">Location<FromCv k="location" /></label><input className={inputClass("location")} value={setupForm.location} onChange={set("location")} /></div>
            <div><label className="label">Phone<FromCv k="phone" /></label><input className={inputClass("phone")} value={setupForm.phone} onChange={set("phone")} /></div>
            <div><label className="label">Email<FromCv k="email" /></label><input className={inputClass("email")} type="email" value={setupForm.email} onChange={set("email")} /></div>
            <div><label className="label">Profession<FromCv k="profession" /></label><input className={inputClass("profession")} value={setupForm.profession} onChange={set("profession")} /></div>
          </div>
          <div><label className="label">Professional registration<FromCv k="professional_registration" /></label><input className={inputClass("professional_registration")} value={setupForm.professional_registration} onChange={set("professional_registration")} /></div>
          <div><label className="label">Summary<FromCv k="summary" /></label><textarea className={inputClass("summary")} rows={3} value={setupForm.summary} onChange={set("summary")} /></div>

          {/* ── Entries found in the CV ───────────────────── */}
          {extras && (extras.education.length > 0 || extras.experience.length > 0 || extras.skills.length > 0) && (
            <div className="space-y-3 rounded-lg border border-slate-200 p-3">
              <div className="text-xs font-semibold uppercase text-slate-400">
                Also found in your CV — untick anything you do not want
              </div>

              {extras.education.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-slate-500 mb-1">Education</div>
                  {extras.education.map((e, i) => (
                    <label key={i} className="flex items-start gap-2 text-sm py-0.5">
                      <input type="checkbox" className="mt-1" checked={chosen.education.includes(i)} onChange={() => toggle("education", i)} />
                      <span>{e.degree}{e.institution ? ` — ${e.institution}` : ""}{e.classification ? ` (${e.classification})` : ""}</span>
                    </label>
                  ))}
                </div>
              )}

              {extras.experience.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-slate-500 mb-1">Experience</div>
                  {extras.experience.map((e, i) => (
                    <label key={i} className="flex items-start gap-2 text-sm py-0.5">
                      <input type="checkbox" className="mt-1" checked={chosen.experience.includes(i)} onChange={() => toggle("experience", i)} />
                      <span>{e.role}{e.organization ? ` — ${e.organization}` : ""}{e.start_date ? ` (${e.start_date}${e.is_current ? "–present" : e.end_date ? `–${e.end_date}` : ""})` : ""}</span>
                    </label>
                  ))}
                </div>
              )}

              {extras.skills.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-slate-500 mb-1">Skills</div>
                  <div className="flex flex-wrap gap-1.5">
                    {extras.skills.map((s, i) => (
                      <label key={i} className={`cursor-pointer rounded-full border px-2 py-0.5 text-xs ${chosen.skills.includes(i) ? "border-brand-300 bg-brand-50 text-brand-700" : "border-slate-200 bg-white text-slate-400"}`}>
                        <input type="checkbox" className="hidden" checked={chosen.skills.includes(i)} onChange={() => toggle("skills", i)} />
                        {s.name}
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <div ref={errRef}>
            <ErrorNote message={err} />
          </div>
          <div className="flex gap-2">
            <button className="btn-primary" disabled={saving}>{saving ? "Saving…" : needsSetup ? "Create profile" : "Save"}</button>
            {!needsSetup && (
              <button type="button" className="btn-secondary" onClick={() => { setForm(null); setExtras(null); setCvFields([]); setCvNotice(""); }}>Cancel</button>
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
