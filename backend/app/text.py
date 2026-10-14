"""Get text out of a PDF or image. PDFs: pdfplumber. Images: RapidOCR (local, no API key) if installed."""
from pathlib import Path


def pdf_text(path: Path) -> str:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


def image_text(path: Path) -> str:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return ""
    result, _ = RapidOCR()(str(path))
    if not result:
        return ""
    # group OCR boxes into lines by vertical centre, then order left-to-right
    boxes = sorted(((sum(p[1] for p in b) / 4, b[0][0], t, b[3][1] - b[0][1]) for b, t, _ in result))
    lines, cur, cy = [], [], None
    for y, x, t, hgt in boxes:
        if cy is not None and abs(y - cy) > max(10, hgt * 0.5):
            lines.append(cur); cur = []
        cur.append((x, t)); cy = y if cy is None or not cur[:-1] else cy
        if len(cur) == 1:
            cy = y
    if cur:
        lines.append(cur)
    return "\n".join(" ".join(t for _, t in sorted(l)) for l in lines)


def extract_text(path: Path, mime: str) -> str:
    if path.suffix.lower() == ".pdf" or "pdf" in (mime or ""):
        return pdf_text(path)
    return image_text(path)
