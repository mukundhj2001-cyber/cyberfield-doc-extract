import os, socket, subprocess, sys, time, tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["DATA_DIR"] = tempfile.mkdtemp()
for k in ("LLM_API_KEY",):
    os.environ.pop(k, None)


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app import main
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="session")
def live_server():
    """Run the real app (with built frontend) on a free port for Playwright."""
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    env = {**os.environ, "DATA_DIR": tempfile.mkdtemp()}
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)], cwd=ROOT / "backend", env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    import httpx
    for _ in range(60):
        try:
            httpx.get(url + "/api/health"); break
        except Exception:
            time.sleep(0.25)
    yield url
    p.terminate()
