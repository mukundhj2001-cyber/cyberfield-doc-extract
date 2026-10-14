import json, os, sqlite3, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_lock = threading.Lock()
SCHEMA = """CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, batch_id TEXT, filename TEXT, stored_path TEXT, mime TEXT,
 doc_type TEXT, status TEXT DEFAULT 'needs_review', mode TEXT, data TEXT, original TEXT, validation TEXT, raw_text TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP, approved_at TEXT, approved_by TEXT);"""


def data_dir() -> Path:
    d = Path(os.environ.get("DATA_DIR", ROOT / "data")); (d / "uploads").mkdir(parents=True, exist_ok=True)
    return d


def connect():
    con = sqlite3.connect(data_dir() / "docs.db", check_same_thread=False); con.row_factory = sqlite3.Row
    return con


def init():
    with _lock, connect() as con:
        con.executescript(SCHEMA)


def q(sql, args=(), one=False):
    with _lock, connect() as con:
        rows = [dict(r) for r in con.execute(sql, args).fetchall()]
    return (rows[0] if rows else None) if one else rows


def x(sql, args=()):
    with _lock, connect() as con:
        cur = con.execute(sql, args); con.commit(); return cur.lastrowid


def doc(row):
    if row:
        for k in ("data", "original", "validation"):
            row[k] = json.loads(row[k]) if row[k] else None
    return row
