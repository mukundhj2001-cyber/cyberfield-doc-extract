"""Business-rule validation run on every extraction and after every human edit."""
import re
from datetime import date, timedelta
from .rules import parse_date, to_number


def _v(data, k):
    return (data.get("fields", {}).get(k) or {}).get("value")


def check(data: dict) -> list[dict]:
    t, out = data.get("doc_type"), []
    add = lambda rule, ok, msg, level="error": out.append({"rule": rule, "status": "pass" if ok else level, "message": msg})
    if t in ("invoice", "receipt"):
        items = data.get("items", [])
        sub, tax, total = (to_number(_v(data, k)) for k in ("subtotal", "tax", "total"))
        req = ["vendor", "invoice_number", "invoice_date", "total"] if t == "invoice" else ["merchant", "date", "total"]
        missing = [k for k in req if _v(data, k) in (None, "")]
        add("required_fields", not missing, "All required fields present" if not missing else f"Missing: {', '.join(missing)}")
        bad = [i["description"] for i in items if i.get("unit_price") is not None and i.get("amount") is not None
               and abs(float(i.get("quantity") or 1) * float(i["unit_price"]) - float(i["amount"])) > 0.05]
        if t == "invoice":
            add("line_math", not bad, "Qty × unit price = amount on every line" if not bad else f"Line math off: {', '.join(bad)}")
        if items and sub is not None:
            s = round(sum(float(i.get("amount") or 0) for i in items), 2)
            add("items_sum_to_subtotal", abs(s - sub) <= 0.05, f"Line items sum to {s:,.2f} vs subtotal {sub:,.2f}")
        if total is not None:
            base = sub if sub is not None else round(sum(float(i.get("amount") or 0) for i in items), 2)
            exp = round(base + (tax or 0), 2)
            add("total_matches", abs(exp - total) <= 0.05, f"Subtotal + tax = {exp:,.2f} vs total {total:,.2f}")
        for k in ("invoice_date", "due_date", "date"):
            v = _v(data, k)
            if v not in (None, ""):
                d = parse_date(str(v))
                ok = d is not None and date(2000, 1, 1) <= date.fromisoformat(d) <= date.today() + timedelta(days=366)
                add(f"{k}_valid", ok, f"{k.replace('_', ' ').title()} {v} is {'a valid date' if ok else 'not a valid/plausible date'}")
        if t == "invoice" and parse_date(str(_v(data, "invoice_date") or "")) and parse_date(str(_v(data, "due_date") or "")):
            ok = parse_date(str(_v(data, "due_date"))) >= parse_date(str(_v(data, "invoice_date")))
            add("due_after_issue", ok, "Due date is on/after invoice date" if ok else "Due date is before invoice date")
    elif t == "resume":
        add("name_present", bool(_v(data, "name")), "Candidate name present" if _v(data, "name") else "Name missing")
        e = _v(data, "email")
        add("email_valid", bool(e and re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.]+", e)), f"Email {e or '(missing)'}")
        p = re.sub(r"\D", "", _v(data, "phone") or "")
        add("phone_valid", 10 <= len(p) <= 15, f"Phone has {len(p)} digits", "warn")
        for i in data.get("items", []):
            s, e2 = parse_date(str(i.get("start") or "")), str(i.get("end") or "")
            en = date.today().isoformat() if e2.lower() in ("present", "current") else parse_date(e2)
            ok = bool(s and en and s <= en)
            add("experience_dates", ok, f"{i.get('title')} @ {i.get('company')}: {i.get('start')} → {i.get('end')}", "warn")
    return out
