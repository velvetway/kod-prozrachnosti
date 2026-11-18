import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="kod-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = _tmp
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

DEMO = Path(__file__).resolve().parents[2] / "demo"


@pytest.fixture(scope="session")
def client():
    from app.main import app
    with TestClient(app) as c:
        assert c.post("/api/login", json={"login": "admin", "password": "admin"}).status_code == 200
        yield c


@pytest.fixture(scope="session")
def demo(client):
    return {d["file"]: d for d in client.get("/api/demo").json()}


def run_demo(client, d, **extra):
    data = {k: str(d[k]) for k in ("region_id", "zone_id", "quarter", "object_type", "capacity", "base_quarter") if d.get(k)}
    data.update({k: str(v) for k, v in extra.items()})
    r = client.post("/api/checks", files={"file": (d["file"], (DEMO / d["file"]).read_bytes())}, data=data)
    assert r.status_code == 200, r.text
    return client.get(f"/api/checks/{r.json()['id']}").json()
