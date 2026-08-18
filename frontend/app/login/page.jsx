"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setSession } from "@/lib/api";
import { ErrorNote } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const tokens = await api("/auth/login", { method: "POST", body: { email, password } });
      setSession(tokens);
      router.replace("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-6">
          <div className="text-white text-2xl font-bold tracking-tight">
            CareerPilot<span className="text-brand-400"> AI</span>
          </div>
          <div className="text-slate-400 text-sm mt-1">Personal career &amp; scholarship agent</div>
        </div>
        <form onSubmit={submit} className="card p-6 space-y-4">
          <div>
            <label className="label">Email</label>
            <input className="input" type="email" value={email} required
              onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </div>
          <div>
            <label className="label">Password</label>
            <input className="input" type="password" value={password} required
              onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </div>
          <ErrorNote message={error} />
          <button className="btn-primary w-full justify-center" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <p className="text-xs text-slate-400 text-center">
            Seeded login: johngichaga8@gmail.com / ChangeMe123!
          </p>
        </form>
      </div>
    </div>
  );
}
