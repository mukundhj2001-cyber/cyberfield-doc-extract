import { useEffect, useState } from "react";
import { api } from "../api";
import { Doc, confColor, TYPE_ICON } from "../types";

const ITEM_COLS: Record<string, string[]> = { invoice: ["description", "quantity", "unit_price", "amount"], receipt: ["description", "quantity", "amount"], resume: ["title", "company", "start", "end"] };
const NUMERIC = new Set(["quantity", "unit_price", "amount", "subtotal", "tax", "total"]);
const label = (k: string) => k.replace(/_/g, " ");

export default function Review({ id }: { id: number }) {
  const [doc, setDoc] = useState<Doc | null>(null);
  const [fields, setFields] = useState<Record<string, any>>({});
  const [items, setItems] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [dirty, setDirty] = useState(false);

  function hydrate(d: Doc) {
    setDoc(d); setFields(Object.fromEntries(Object.entries(d.data.fields).map(([k, v]) => [k, v.value ?? ""]))); setItems(d.data.items.map((i) => ({ ...i }))); setDirty(false);
  }
  useEffect(() => { api<Doc>(`/api/documents/${id}`).then(hydrate); }, [id]);
  if (!doc) return <div className="text-zinc-500">Loading…</div>;

  const cast = (k: string, v: any) => (NUMERIC.has(k) && v !== "" && !isNaN(+v) ? +v : v === "" ? null : v);
  async function save() {
    const d = await api<Doc>(`/api/documents/${id}`, { method: "PUT", body: JSON.stringify({ fields: Object.fromEntries(Object.entries(fields).map(([k, v]) => [k, cast(k, v)])),
      items: items.map((i) => Object.fromEntries(Object.entries(i).map(([k, v]) => [k, k === "confidence" ? v : cast(k, v)]))) }) });
    hydrate(d); setMsg("Saved — validation re-run."); return d;
  }
  async function approve(force = false) {
    if (dirty) await save();
    const r = await fetch(`/api/documents/${id}/approve?force=${force}`, { method: "POST" });
    if (r.ok) { hydrate(await r.json()); setMsg("✅ Approved and ready for export."); }
    else setMsg("Validation errors must be fixed first — or approve with override.");
  }
  async function reject() { hydrate(await api(`/api/documents/${id}/reject`, { method: "POST" })); setMsg("Rejected."); }

  const errors = doc.validation.filter((c) => c.status === "error").length;
  const cols = ITEM_COLS[doc.doc_type];
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <a href="#/" className="text-sm text-zinc-400 hover:text-gold-300">← All documents</a>
        <h1 className="text-xl font-bold">{TYPE_ICON[doc.doc_type]} {doc.filename}</h1>
        <span className="chip bg-gold-500/15 text-gold-300 capitalize">{doc.doc_type} · {Math.round(doc.data.type_confidence * 100)}%</span>
        <span className="chip bg-white/10 text-zinc-300">extracted by {doc.mode === "llm" ? "LLM" : "local rules"}</span>
        <span data-testid="doc-status" className={`chip ${doc.status === "approved" ? "bg-emerald-500/20 text-emerald-300" : doc.status === "rejected" ? "bg-red-500/20 text-red-300" : "bg-amber-500/20 text-amber-300"}`}>{doc.status.replace("_", " ")}</span>
      </div>
      <div className="grid lg:grid-cols-[1fr_1.1fr] gap-6 items-start">
        <div className="card overflow-hidden h-[78vh] bg-white relative">
          <a href={`/api/documents/${id}/file`} target="_blank" className="absolute top-2 right-2 chip bg-black/70 text-gold-300">Open original ↗</a>
          <img src={`/api/documents/${id}/preview`} alt="document preview" className="w-full h-full object-contain object-top bg-zinc-100" />
        </div>
        <div className="space-y-4">
          {doc.data.warning && <div className="card p-3 text-sm text-amber-300">{doc.data.warning}</div>}
          <div className="card p-4">
            <div className="flex items-center mb-3"><div className="font-semibold text-gold-300">Extracted fields</div>
              <div className="ml-auto flex gap-3 text-[11px] text-zinc-500"><span>● <span className="text-emerald-400">≥90%</span></span><span>● <span className="text-gold-400">75–90%</span></span><span>● <span className="text-red-400">&lt;75% check</span></span></div></div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-3" data-testid="fields">
              {Object.entries(doc.data.fields).map(([k, f]) => (
                <label key={k} className={k === "skills" || k === "bill_to" ? "col-span-2" : ""}>
                  <div className="flex items-center text-xs text-zinc-400 capitalize mb-1">{label(k)}
                    <span className="ml-auto flex items-center gap-1.5">{f.edited ? <span className="text-sky-300">edited</span> : <>
                      <span className={`h-1.5 w-10 rounded bg-white/10 overflow-hidden`}><span className={`block h-1.5 ${confColor(f.confidence)}`} style={{ width: `${f.confidence * 100}%` }} /></span>{Math.round(f.confidence * 100)}%</>}</span></div>
                  <input data-testid={`field-${k}`} className={`input ${!f.edited && f.confidence < 0.75 ? "!border-red-400/60" : ""}`} value={fields[k] ?? ""}
                    onChange={(e) => { setFields({ ...fields, [k]: e.target.value }); setDirty(true); }} />
                </label>))}
            </div>
          </div>
          <div className="card p-4" data-testid="validation">
            <div className="font-semibold text-gold-300 mb-2">Validation</div>
            <ul className="space-y-1.5 text-sm">{doc.validation.map((c, i) => (
              <li key={i} className="flex gap-2"><span>{c.status === "pass" ? "✅" : c.status === "warn" ? "⚠️" : "❌"}</span><span className={c.status === "error" ? "text-red-300" : "text-zinc-300"}>{c.message}</span></li>))}</ul>
          </div>
          <div className="card p-4">
            <div className="flex items-center mb-2"><div className="font-semibold text-gold-300">{doc.doc_type === "resume" ? "Experience" : "Line items"}</div>
              <button className="btn-ghost !py-1 ml-auto text-xs" onClick={() => { setItems([...items, Object.fromEntries(cols.map((c) => [c, ""]))]); setDirty(true); }}>+ Add row</button></div>
            <table className="w-full"><thead><tr>{cols.map((c) => <th key={c} className="capitalize">{label(c)}</th>)}<th></th></tr></thead>
              <tbody>{items.map((it, i) => (<tr key={i}>{cols.map((c) => (
                <td key={c} className="!px-1 !py-1"><input className={`input !py-1 ${NUMERIC.has(c) ? "text-right" : ""}`} value={it[c] ?? ""} onChange={(e) => { const n = [...items]; n[i] = { ...n[i], [c]: e.target.value }; setItems(n); setDirty(true); }} /></td>))}
                <td className="!px-1"><button className="text-zinc-500 hover:text-red-300" onClick={() => { setItems(items.filter((_, j) => j !== i)); setDirty(true); }}>✕</button></td></tr>))}</tbody></table>
          </div>
          <div className="flex items-center gap-2 card p-3">
            <button className="btn-ghost" onClick={save} disabled={!dirty}>Save edits</button>
            <button className="btn-gold" data-testid="approve" onClick={() => approve(false)}>{errors && !dirty ? `Approve (${errors} issue${errors > 1 ? "s" : ""})` : "Approve"}</button>
            {errors > 0 && <button className="btn-ghost" onClick={() => approve(true)}>Approve with override</button>}
            <button className="btn-ghost !text-red-300 !border-red-400/30" onClick={reject}>Reject</button>
            <span className="text-sm text-zinc-400 ml-2" data-testid="msg">{msg}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
