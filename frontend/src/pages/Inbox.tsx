import { useEffect, useRef, useState } from "react";
import { api, post } from "../api";
import { Doc, avgConf, confColor, TYPE_ICON } from "../types";

const StatusChip = ({ s }: { s: string }) => {
  const c: Record<string, string> = { approved: "bg-emerald-500/15 text-emerald-300", needs_review: "bg-amber-500/15 text-amber-300", rejected: "bg-red-500/15 text-red-300" };
  return <span className={`chip ${c[s]}`}>{s.replace("_", " ")}</span>;
};

export default function Inbox() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [busy, setBusy] = useState("");
  const [drag, setDrag] = useState(false);
  const [scope, setScope] = useState("approved");
  const input = useRef<HTMLInputElement>(null);
  const load = () => api<Doc[]>("/api/documents").then(setDocs);
  useEffect(() => { load(); }, []);

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    const fd = new FormData(); Array.from(files).forEach((f) => fd.append("files", f));
    setBusy(`Extracting ${files.length} document${files.length > 1 ? "s" : ""}…`);
    try { await fetch("/api/documents", { method: "POST", body: fd }); await load(); } finally { setBusy(""); }
  }
  async function samples() { setBusy("Processing sample documents…"); try { await post("/api/samples/load"); await load(); } finally { setBusy(""); } }

  const counts = { total: docs.length, review: docs.filter((d) => d.status === "needs_review").length, approved: docs.filter((d) => d.status === "approved").length,
    issues: docs.filter((d) => d.validation.some((c) => c.status === "error")).length };

  return (
    <div className="space-y-6">
      <div className="grid lg:grid-cols-[1.3fr_1fr] gap-6">
        <div>
          <h1 className="font-display text-3xl font-bold leading-tight"><span className="gold-text">Invoices, receipts & resumes</span><br />to clean data in seconds</h1>
          <p className="text-zinc-400 text-sm mt-3 max-w-xl">We built this pipeline to pull structured fields out of PDFs and photos, score each field's confidence, check the maths, and keep a human in the loop before anything is exported.</p>
          <div className="grid grid-cols-4 gap-3 mt-5" data-testid="kpis">
            {[["Documents", counts.total], ["Needs review", counts.review], ["Approved", counts.approved], ["Validation issues", counts.issues]].map(([l, v]) => (
              <div key={l} className="card p-3"><div className="text-[11px] uppercase tracking-wider text-zinc-500">{l}</div><div className="text-2xl font-bold gold-text">{v}</div></div>))}
          </div>
        </div>
        <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}
          className={`card border-2 border-dashed p-6 grid place-items-center text-center transition ${drag ? "border-gold-400 bg-gold-500/10" : "border-gold-500/30"}`}>
          <div className="space-y-3">
            <div className="text-4xl">📄</div>
            <div className="font-semibold">Drop PDFs or images here</div>
            <div className="text-xs text-zinc-500">Batch upload supported · PDF, PNG, JPG</div>
            <input ref={input} data-testid="file-input" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.webp" className="hidden" onChange={(e) => upload(e.target.files)} />
            <div className="flex gap-2 justify-center">
              <button className="btn-gold" onClick={() => input.current?.click()}>Choose files</button>
              <button className="btn-ghost" data-testid="load-samples" onClick={samples}>Try 7 sample documents</button>
            </div>
            {busy && <div className="text-sm text-gold-300 animate-pulse">{busy}</div>}
          </div>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-3 border-b border-white/5">
          <div className="font-semibold">Documents</div>
          <div className="ml-auto flex items-center gap-2 text-sm">
            <span className="text-zinc-500">Export</span>
            <select className="input !w-auto !py-1.5" value={scope} onChange={(e) => setScope(e.target.value)}>
              <option value="approved">approved only</option><option value="all">all documents</option></select>
            {(["csv", "xlsx", "json"] as const).map((f) => (
              <a key={f} data-testid={`export-${f}`} className="btn-ghost !py-1.5" href={`/api/export?format=${f}&status=${scope}`}>{f === "xlsx" ? "Excel" : f.toUpperCase()}</a>))}
          </div>
        </div>
        <table className="w-full" data-testid="doc-table">
          <thead><tr><th>Document</th><th>Type</th><th>Key value</th><th>Confidence</th><th>Validation</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {docs.length === 0 && <tr><td colSpan={7} className="text-center text-zinc-500 py-10">No documents yet — upload some or try the samples.</td></tr>}
            {docs.map((d) => {
              const f = d.data.fields, c = avgConf(d), errs = d.validation.filter((x) => x.status === "error").length;
              const key = d.doc_type === "resume" ? f.name?.value : `${f.currency?.value ?? ""} ${f.total?.value?.toLocaleString?.() ?? f.total?.value ?? "–"}`;
              return (
                <tr key={d.id} className="hover:bg-white/5 cursor-pointer" onClick={() => (location.hash = `#/review/${d.id}`)}>
                  <td><div className="font-medium">{d.filename}</div><div className="text-xs text-zinc-500">{d.data.fields.vendor?.value ?? d.data.fields.merchant?.value ?? d.data.fields.headline?.value}</div></td>
                  <td className="capitalize">{TYPE_ICON[d.doc_type]} {d.doc_type}</td>
                  <td className="font-semibold text-gold-200">{key}</td>
                  <td><div className="flex items-center gap-2"><div className="h-1.5 w-20 rounded bg-white/10"><div className={`h-1.5 rounded ${confColor(c)}`} style={{ width: `${c * 100}%` }} /></div><span className="text-xs text-zinc-400">{Math.round(c * 100)}%</span></div></td>
                  <td>{errs ? <span className="chip bg-red-500/15 text-red-300">⚠ {errs} issue{errs > 1 ? "s" : ""}</span> : <span className="chip bg-emerald-500/15 text-emerald-300">✓ checks pass</span>}</td>
                  <td><StatusChip s={d.status} /></td>
                  <td><span className="text-gold-400 text-sm">Review →</span></td>
                </tr>);
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
