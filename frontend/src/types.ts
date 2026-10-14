export type Field = { value: any; confidence: number; edited?: boolean };
export type Check = { rule: string; status: "pass" | "error" | "warn"; message: string };
export type Doc = { id: number; filename: string; doc_type: "invoice" | "receipt" | "resume"; status: string; mode: string; mime: string;
  created_at: string; data: { fields: Record<string, Field>; items: any[]; type_confidence: number; warning?: string }; validation: Check[] };
export const avgConf = (d: Doc) => { const v = Object.values(d.data.fields).filter((f) => f.value !== null && f.value !== ""); return v.length ? v.reduce((a, f) => a + f.confidence, 0) / v.length : 0; };
export const confColor = (c: number) => (c >= 0.9 ? "bg-emerald-400" : c >= 0.75 ? "bg-gold-400" : "bg-red-400");
export const TYPE_ICON: Record<string, string> = { invoice: "🧾", receipt: "🛍️", resume: "👤" };
