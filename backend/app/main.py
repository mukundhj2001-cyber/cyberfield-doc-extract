"""Cyberfield Doc Extract — FastAPI app."""
import json, mimetypes, shutil, uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import db, exporter, llm, rules, text, validate

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "samples"
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


@asynccontextmanager
async def lifespan(_):
    db.init(); yield

app = FastAPI(title="Cyberfield Doc Extract", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def process(path: Path, filename: str, mime: str, batch: str, doc_type: str | None = None) -> dict:
    raw = text.extract_text(path, mime)
    is_img = path.suffix.lower() != ".pdf"
    dtype = doc_type or rules.classify(raw, filename)[0]
    data, mode = None, "mock"
    if llm.enabled():
        data = llm.extract(raw, dtype, image=path if is_img else None)
        if data:
            data.update(doc_type=dtype, type_confidence=0.95); mode = "llm"
    if not data:
        data = rules.extract(raw, filename, doc_type)
        if is_img:  # OCR adds uncertainty
            for f in data["fields"].values():
                f["confidence"] = round(f["confidence"] * 0.92, 2)
        if not raw.strip():
            data["warning"] = "No text found. Install rapidocr-onnxruntime for local OCR, or set LLM_API_KEY to use a vision model."
    checks = validate.check(data)
    did = db.x("INSERT INTO documents(batch_id,filename,stored_path,mime,doc_type,mode,data,original,validation,raw_text) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (batch, filename, str(path), mime, data["doc_type"], mode, json.dumps(data), json.dumps(data), json.dumps(checks), raw))
    return get(did)


@app.get("/api/health")
def health():
    return {"ok": True, "mode": "llm" if llm.enabled() else "mock"}


@app.post("/api/documents")
async def upload(files: list[UploadFile] = File(...), doc_type: str | None = Query(None)):
    if doc_type and doc_type not in rules.SCHEMAS:
        raise HTTPException(400, "doc_type must be invoice, receipt or resume")
    batch, out = uuid.uuid4().hex[:8], []
    for f in files:
        ext = Path(f.filename or "").suffix.lower()
        if ext not in ALLOWED:
            out.append({"filename": f.filename, "error": f"Unsupported file type {ext}"}); continue
        dest = db.data_dir() / "uploads" / f"{uuid.uuid4().hex}{ext}"
        with dest.open("wb") as fh:
            shutil.copyfileobj(f.file, fh)
        out.append(process(dest, f.filename, f.content_type or mimetypes.guess_type(dest.name)[0] or "", batch, doc_type))
    return {"batch_id": batch, "documents": out}


@app.post("/api/samples/load")
def load_samples():
    batch, out = "samples", []
    for p in sorted(SAMPLES.iterdir()):
        if p.suffix.lower() in ALLOWED:
            dest = db.data_dir() / "uploads" / f"{uuid.uuid4().hex}{p.suffix.lower()}"
            shutil.copy(p, dest)
            out.append(process(dest, p.name, mimetypes.guess_type(p.name)[0] or "", batch))
    return {"batch_id": batch, "documents": out}


@app.get("/api/samples")
def list_samples():
    return [p.name for p in sorted(SAMPLES.iterdir()) if p.suffix.lower() in ALLOWED]


@app.get("/api/documents")
def list_docs(status: str | None = None):
    rows = db.q("SELECT * FROM documents ORDER BY id DESC")
    docs = [db.doc(r) for r in rows if not status or r["status"] == status]
    for d in docs:
        d.pop("raw_text", None); d.pop("original", None)
    return docs


@app.get("/api/documents/{did}")
def get(did: int):
    d = db.doc(db.q("SELECT * FROM documents WHERE id=?", (did,), one=True))
    if not d:
        raise HTTPException(404)
    return d


@app.get("/api/documents/{did}/file")
def file(did: int):
    d = get(did)
    return FileResponse(d["stored_path"], media_type=d["mime"] or None, filename=d["filename"], content_disposition_type="inline")


@app.get("/api/documents/{did}/preview")
def preview(did: int, page: int = 0):
    """PNG preview of the document (PDF pages rendered with pdfium, so no browser PDF viewer is needed)."""
    d = get(did)
    path = Path(d["stored_path"])
    if path.suffix.lower() != ".pdf":
        return FileResponse(path)
    import io, pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(str(path))
    img = pdf[min(page, len(pdf) - 1)].render(scale=2).to_pil()
    buf = io.BytesIO(); img.save(buf, "PNG")
    return Response(buf.getvalue(), media_type="image/png")


class EditIn(BaseModel):
    fields: dict[str, object]
    items: list[dict] | None = None
    doc_type: str | None = None


@app.put("/api/documents/{did}")
def edit(did: int, e: EditIn):
    d = get(did)
    data = d["data"]
    for k, v in e.fields.items():
        old = data["fields"].get(k, {})
        if old.get("value") != v:
            data["fields"][k] = {"value": v, "confidence": 1.0, "edited": True}
    if e.items is not None:
        data["items"] = e.items
    checks = validate.check(data)
    db.x("UPDATE documents SET data=?, validation=?, status=CASE WHEN status='approved' THEN 'needs_review' ELSE status END WHERE id=?",
         (json.dumps(data), json.dumps(checks), did))
    return get(did)


@app.post("/api/documents/{did}/approve")
def approve(did: int, force: bool = False, reviewer: str = "reviewer"):
    d = get(did)
    errors = [c for c in d["validation"] or [] if c["status"] == "error"]
    if errors and not force:
        raise HTTPException(422, {"message": "Validation errors — fix them or approve with override", "errors": errors})
    db.x("UPDATE documents SET status='approved', approved_at=CURRENT_TIMESTAMP, approved_by=? WHERE id=?", (reviewer + (" (override)" if errors else ""), did))
    return get(did)


@app.post("/api/documents/{did}/reject")
def reject(did: int):
    get(did); db.x("UPDATE documents SET status='rejected' WHERE id=?", (did,)); return get(did)


@app.delete("/api/documents")
def clear():
    db.x("DELETE FROM documents"); return {"ok": True}


@app.get("/api/export")
def export(format: str = "json", status: str = "approved", doc_type: str | None = None):
    docs = [get(r["id"]) for r in db.q("SELECT id FROM documents ORDER BY id")]
    docs = [d for d in docs if (status == "all" or d["status"] == status) and (not doc_type or d["doc_type"] == doc_type)]
    name = f"cyberfield-extract-{status}"
    if format == "csv":
        return Response(exporter.to_csv(docs), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
    if format == "xlsx":
        return Response(exporter.to_xlsx(docs), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'})
    return Response(exporter.to_json(docs), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{name}.json"'})


DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
