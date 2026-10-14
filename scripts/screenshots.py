"""Capture README screenshots into docs/screenshots (needs frontend/dist)."""
import os, subprocess, sys, tempfile, time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"; OUT.mkdir(parents=True, exist_ok=True)
srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8812"], cwd=ROOT / "backend",
                       env={**os.environ, "DATA_DIR": tempfile.mkdtemp()})
URL = "http://127.0.0.1:8812"
for _ in range(60):
    try: httpx.get(URL + "/api/health"); break
    except Exception: time.sleep(0.25)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.goto(URL); pg.wait_for_timeout(500)
        pg.screenshot(path=OUT / "01-upload-empty.png")
        docs = httpx.post(URL + "/api/samples/load", timeout=120).json()["documents"]
        ids = {d["filename"]: d["id"] for d in docs}
        httpx.post(URL + f"/api/documents/{ids['resume_daniel_okafor.pdf']}/approve")
        httpx.post(URL + f"/api/documents/{ids['receipt_cafe_aroma.pdf']}/approve")
        pg.reload(); pg.wait_for_timeout(800)
        pg.screenshot(path=OUT / "02-batch-results.png", full_page=True)
        for n, fname in [("03-review-invoice.png", "invoice_nimbus_cloud.pdf"), ("04-validation-error.png", "invoice_harbor_supplies_mismatch.pdf"),
                         ("05-review-receipt-image-ocr.png", "receipt_freshmart.png"), ("06-review-resume.png", "resume_ananya_iyer.pdf")]:
            pg.goto(f"{URL}/#/review/{ids[fname]}"); pg.wait_for_timeout(1500)
            pg.screenshot(path=OUT / n, full_page=True)
        pg.goto(f"{URL}/#/review/{ids['invoice_harbor_supplies_mismatch.pdf']}"); pg.wait_for_timeout(1000)
        pg.get_by_test_id("field-total").fill("19809.84"); pg.get_by_test_id("approve").click(); pg.wait_for_timeout(1000)
        pg.screenshot(path=OUT / "07-fixed-and-approved.png", full_page=True)
        b.close()
    # Excel export preview: render the first sheet as a simple HTML table screenshot
    import io
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(httpx.get(URL + "/api/export?format=xlsx&status=all").content))
    html = "<body style='font-family:Segoe UI,Arial;background:#0b0b0f;color:#eee;padding:20px'>"
    for name in wb.sheetnames[:2]:
        ws = wb[name]; html += f"<h3 style='color:#D4AF37'>{name}.xlsx sheet</h3><table style='border-collapse:collapse;font-size:12px'>"
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            html += "<tr>" + "".join(f"<td style='border:1px solid #333;padding:4px 8px;{'background:#D4AF37;color:#000;font-weight:bold' if i == 0 else ''}'>{'' if v is None else v}</td>" for v in row) + "</tr>"
        html += "</table>"
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 600}); pg.set_content(html)
        pg.screenshot(path=OUT / "08-excel-export.png", full_page=True); b.close()
finally:
    srv.terminate()
print("saved to", OUT)
