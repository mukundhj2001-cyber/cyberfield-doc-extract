"""Mock-mode extractor: deterministic regex/heuristic rules over document text, with per-field confidence."""
import re
from datetime import datetime

MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
NUM = r"[-+]?(?:Rs\.?|INR|₹|\$|USD|EUR|€|£)?\s?\d[\d,]*(?:\.\d{1,2})?"
SCHEMAS = {
    "invoice": {"fields": ["vendor", "invoice_number", "invoice_date", "due_date", "bill_to", "currency", "subtotal", "tax", "total"],
                "items": ["description", "quantity", "unit_price", "amount"]},
    "receipt": {"fields": ["merchant", "receipt_number", "date", "payment_method", "currency", "subtotal", "tax", "total"],
                "items": ["description", "quantity", "amount"]},
    "resume": {"fields": ["name", "headline", "email", "phone", "location", "links", "skills", "education"],
               "items": ["title", "company", "start", "end"]},
}


def F(value, confidence):
    return {"value": value, "confidence": round(confidence, 2) if value not in (None, "") else 0.0}


def to_number(s):
    if s is None:
        return None
    s = re.sub(r"(Rs\.?|INR|₹|\$|USD|EUR|€|£|\s)", "", str(s)).replace(",", "")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def parse_date(s):
    """Return ISO date string or None. Numeric dates are read day-first (dd/mm/yyyy)."""
    if not s:
        return None
    s = s.strip().rstrip(".,")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y", "%b %Y", "%B %Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


DATE_RX = rf"(\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}|(?:{MONTHS})[a-z]*\.? \d{{1,2}}, \d{{4}}|\d{{1,2}} (?:{MONTHS})[a-z]* \d{{4}})"


def labelled(text, labels, value_rx=r"(.+)"):
    for lab in labels:
        m = re.search(rf"(?im)^.*?\b{lab}\b\s*[:#.]?\s*(?:no\.?|number)?\s*[:#]?\s*{value_rx}", text)
        if m:
            return m.group(1).strip()
    return None


def currency(text):
    if re.search(r"Rs\.?|INR|₹|GSTIN|GST", text):
        return "INR"
    if "$" in text or "USD" in text:
        return "USD"
    if "€" in text:
        return "EUR"
    if "£" in text:
        return "GBP"
    return None


def classify(text: str, filename: str = "") -> tuple[str, float]:
    t = text.lower(); fn = filename.lower()
    scores = {
        "resume": sum(k in t for k in ("experience", "skills", "education", "summary", "linkedin", "github")) + 2 * ("resume" in fn or "cv" in fn),
        "invoice": sum(k in t for k in ("invoice", "bill to", "due date", "gstin", "unit price")) + 2 * ("invoice" in fn),
        "receipt": sum(k in t for k in ("receipt", "cashier", "paid by", "thank you", "change")) + 2 * ("receipt" in fn),
    }
    best = max(scores, key=scores.get)
    total = sum(scores.values()) or 1
    return best, round(min(0.99, 0.5 + 0.5 * scores[best] / total), 2) if scores[best] else 0.3


def money_line(text, labels):
    for lab in labels:
        m = re.search(rf"(?im)^\s*{lab}\b[^\n\d$₹]*?(?:\([^)]*\))?\s*:?\s*({NUM})\s*$", text)
        if m:
            return to_number(m.group(1))
    return None


def tax_line(text):
    m = re.search(rf"(?im)^\s*((?:c?gst|s?gst|igst|vat|sales tax|tax)\b[^\n]*?)\s*:?\s*({NUM})\s*$", text)
    return to_number(m.group(2)) if m else None


def first_nonheader_line(lines):
    for l in lines:
        if not re.fullmatch(r"(tax )?invoice|receipt|bill|cash memo", l.strip().lower()) and len(l.strip()) > 2:
            return l.strip()
    return None


def invoice_items(text):
    items = []
    rx = re.compile(rf"^(?P<d>[A-Za-z][^\n]*?)\s+(?P<q>\d+(?:\.\d+)?)\s+(?P<u>{NUM})\s+(?P<a>{NUM})\s*$", re.M)
    for m in rx.finditer(text):
        q, u, a = float(m["q"]), to_number(m["u"]), to_number(m["a"])
        conf = 0.95 if u is not None and a is not None and abs(q * u - a) < 0.05 else 0.6
        items.append({"description": m["d"].strip(), "quantity": q, "unit_price": u, "amount": a, "confidence": conf})
    return items


def receipt_items(text):
    items = []
    for m in re.finditer(r"(?im)^\s*(\d+)\s*[xX×]\s*(.+?)\s+(\d[\d,]*\.\d{2})\s*$", text):
        items.append({"description": m[2].strip(), "quantity": float(m[1]), "amount": to_number(m[3]), "confidence": 0.9})
    return items


def extract_invoice(text):
    lines = [l for l in text.splitlines() if l.strip()]
    vendor = first_nonheader_line(lines)
    bill = None
    m = re.search(r"(?im)^bill(?:ed)? to:?\s*\n?(.+)$", text)
    if m:
        bill = m.group(1).strip() or None
    inv_date = labelled(text, ["invoice date", "date of issue", "date"], DATE_RX)
    due = labelled(text, ["due date", "payment due"], DATE_RX)
    num = labelled(text, ["invoice no", "invoice number", "invoice #", "invoice"], r"([A-Z0-9][A-Z0-9/\-_.]{2,})")
    return {
        "fields": {
            "vendor": F(vendor, 0.8), "invoice_number": F(num, 0.95), "invoice_date": F(parse_date(inv_date), 0.93 if parse_date(inv_date) else 0.4),
            "due_date": F(parse_date(due), 0.9), "bill_to": F(bill, 0.85), "currency": F(currency(text), 0.8),
            "subtotal": F(money_line(text, ["sub ?total", "subtotal"]), 0.92), "tax": F(tax_line(text), 0.85),
            "total": F(money_line(text, ["grand total", "total amount", "amount due", "total"]), 0.95)},
        "items": invoice_items(text)}


def extract_receipt(text):
    lines = [l for l in text.splitlines() if l.strip()]
    num = labelled(text, ["receipt no", "receipt number", "receipt #", "receipt", "bill no"], r"([A-Z0-9][A-Z0-9/\-_.]{2,})")
    d = labelled(text, ["date"], DATE_RX)
    pay = labelled(text, ["paid by", "payment method", "payment", "tender"], r"([A-Za-z ]+)")
    total = money_line(text, ["total", "grand total", "amount paid"])
    return {
        "fields": {
            "merchant": F(first_nonheader_line(lines), 0.85), "receipt_number": F(num, 0.9), "date": F(parse_date(d), 0.9),
            "payment_method": F(pay.strip() if pay else None, 0.85), "currency": F(currency(text) or "INR", 0.6),
            "subtotal": F(money_line(text, ["sub ?total"]), 0.9), "tax": F(tax_line(text), 0.85), "total": F(total, 0.95)},
        "items": receipt_items(text)}


SECTIONS = r"summary|profile|skills|technical skills|experience|work experience|employment|education|projects|certifications"


def section(text, name):
    m = re.search(rf"(?ims)^\s*(?:{name})\s*:?\s*$\n(.*?)(?=^\s*(?:{SECTIONS})\s*:?\s*$|\Z)", text)
    return m.group(1).strip() if m else ""


def extract_resume(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    phone = re.search(r"\+?\d[\d ()\-]{8,}\d", text)
    links = re.findall(r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com|[\w-]+\.(?:dev|io|me))/[\w\-/]+", text)
    name = lines[0] if lines and not re.search(r"@|\d", lines[0]) else None
    headline = lines[1] if len(lines) > 1 and not re.search(r"@|\d", lines[1]) else None
    contact_line = next((l for l in lines if email and email.group() in l), "")
    loc = next((p.strip() for p in contact_line.split("|") if re.fullmatch(r"[A-Za-z .]+, ?[A-Za-z .]+", p.strip())), None)
    skills = [s.strip() for s in re.split(r"[,•|\n]", section(text, "skills|technical skills")) if s.strip()]
    exp = []
    block = section(text, "experience|work experience|employment").splitlines()
    for i, l in enumerate(block):
        m = re.match(r"^(.+?)\s+[-–|@,]\s+(.+)$", l)
        nxt = block[i + 1] if i + 1 < len(block) else ""
        d = re.match(rf"(?i)^((?:{MONTHS})[a-z]* \d{{4}}|\d{{4}})\s*[-–to]+\s*((?:{MONTHS})[a-z]* \d{{4}}|\d{{4}}|present|current)$", nxt.strip())
        if m and d and not l.startswith("-"):
            exp.append({"title": m[1].strip(), "company": m[2].strip(), "start": d[1], "end": d[2], "confidence": 0.9})
    edu = section(text, "education").splitlines()
    return {
        "fields": {
            "name": F(name, 0.9), "headline": F(headline, 0.75), "email": F(email.group() if email else None, 0.98),
            "phone": F(phone.group().strip() if phone else None, 0.92), "location": F(loc, 0.7), "links": F(", ".join(links) or None, 0.9),
            "skills": F(", ".join(skills) or None, 0.88), "education": F(edu[0] if edu else None, 0.8)},
        "items": exp}


def extract(text: str, filename: str = "", doc_type: str | None = None) -> dict:
    dt, conf = (doc_type, 1.0) if doc_type else classify(text, filename)
    out = {"invoice": extract_invoice, "receipt": extract_receipt, "resume": extract_resume}[dt](text)
    out["doc_type"] = dt
    out["type_confidence"] = conf
    return out
