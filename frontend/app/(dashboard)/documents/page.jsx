"use client";

import { useState } from "react";
import { api, upload } from "@/lib/api";
import { useAsync, Spinner, ErrorNote, EmptyState, Badge } from "@/components/ui";

const TYPES = ["CV", "TRANSCRIPT", "DEGREE", "TSC", "TEACHING_PRACTICE", "RECOMMENDATION", "PORTFOLIO", "OTHER"];

export default function DocumentsPage() {
  const docs = useAsync(() => api("/documents"));
  const [file, setFile] = useState(null);
  const [type, setType] = useState("CV");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    if (!file) return;
    setErr(""); setMsg("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      await upload(`/documents/upload?doc_type=${type}`, fd);
      setMsg("Uploaded — extraction will be processed in a later phase.");
      setFile(null);
      docs.reload();
    } catch (ex) {
      setErr(ex.message);
    }
  };

  const del = async (id) => {
    setErr(""); setMsg("");
    try {
      await api(`/documents/${id}`, { method: "DELETE" });
      docs.reload();
    } catch (ex) {
      setErr(ex.message);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Documents</h1>
        <p className="text-sm text-slate-500">Certificates, transcripts, TSC records and more — stored securely.</p>
      </div>

      <form onSubmit={submit} className="card p-4 space-y-3">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <label className="label">File (PDF, DOCX, TXT or image)</label>
            <input className="input" type="file" accept=".pdf,.docx,.doc,.txt,.png,.jpg,.jpeg"
              onChange={(e) => setFile(e.target.files[0] || null)} />
          </div>
          <div>
            <label className="label">Document type</label>
            <select className="input" value={type} onChange={(e) => setType(e.target.value)}>
              {TYPES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button className="btn-primary" disabled={!file}>Upload</button>
          {msg && <span className="text-sm text-emerald-700">{msg}</span>}
        </div>
        <ErrorNote message={err} />
      </form>

      {docs.loading ? <Spinner /> : docs.data?.length === 0 ? (
        <EmptyState text="No documents yet." />
      ) : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
          {docs.data.map((d) => (
            <div key={d.id} className="card p-4 flex flex-col gap-2">
              <div className="font-medium text-slate-900 truncate">{d.file_name}</div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Badge>{d.doc_type}</Badge>
                <span>{d.extraction_status}</span>
              </div>
              <button className="btn-danger mt-auto self-start" onClick={() => del(d.id)}>Delete</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
