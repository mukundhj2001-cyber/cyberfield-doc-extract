"""Real mode: OpenAI-compatible LLM extraction (text, or vision for images). Enabled when LLM_API_KEY is set."""
import base64, json, os, re
from pathlib import Path
import httpx
from .rules import SCHEMAS


def enabled():
    return bool(os.environ.get("LLM_API_KEY"))


def extract(text: str, doc_type: str, image: Path | None = None) -> dict | None:
    if not enabled():
        return None
    s = SCHEMAS[doc_type]
    prompt = (f"Extract a {doc_type} into JSON with this exact shape: "
              f'{{"fields": {{{", ".join(f"{chr(34)}{k}{chr(34)}: {{{chr(34)}value{chr(34)}: ..., {chr(34)}confidence{chr(34)}: 0-1}}" for k in s["fields"])}}}, '
              f'"items": [{{{", ".join(f"{chr(34)}{k}{chr(34)}: ..." for k in s["items"])}, "confidence": 0-1}}]}}. '
              "Dates as YYYY-MM-DD (resume dates as 'Mon YYYY' or 'Present'), money as plain numbers, skills comma-separated. "
              "Use null for anything not present. Confidence reflects how sure you are. Return JSON only.")
    content = [{"type": "text", "text": prompt + ("\n\nDOCUMENT TEXT:\n" + text[:15000] if text else "")}]
    if image is not None:
        b64 = base64.b64encode(image.read_bytes()).decode()
        mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
    try:
        r = httpx.post(os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/") + "/chat/completions", timeout=60,
                       headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
                       json={"model": os.environ.get("LLM_MODEL", "gpt-4o-mini"), "temperature": 0,
                             "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": content}]})
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"]
        data = json.loads(re.search(r"\{.*\}", raw, re.S).group())
        data["fields"] = {k: (v if isinstance(v, dict) else {"value": v, "confidence": 0.8}) for k, v in data.get("fields", {}).items()}
        return data
    except Exception:
        return None
