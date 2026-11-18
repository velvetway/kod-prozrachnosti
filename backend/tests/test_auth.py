from fastapi.testclient import TestClient

from conftest import run_demo


def _anon():
    from app.main import app
    return TestClient(app)


def test_requires_login():
    c = _anon()
    assert c.get("/api/checks").status_code == 401
    assert c.get("/api/health").status_code == 200
    assert c.post("/api/login", json={"login": "admin", "password": "wrong"}).status_code == 401


def test_specialist_cannot_import_reference(demo):
    c = _anon()
    assert c.post("/api/login", json={"login": "specialist", "password": "specialist"}).status_code == 200
    assert c.get("/api/me").json()["role"] == "specialist"
    r = c.post("/api/reference/import", data={"kind": "prices"}, files={"file": ("p.csv", b"source\n")})
    assert r.status_code == 403
    assert c.get("/api/audit").status_code == 403
    # специалист проверяет документы и принимает решения
    check = run_demo(c, demo["01_bryansk_school_smeta.xlsx"])
    sig = next(s for it in check["items"] for s in it["signals"] if s["level"] == "high")
    d = c.post(f"/api/signals/{sig['id']}/decision", json={"outcome": "Запросить обоснование цены"}).json()
    assert d["decisions"][-1]["author"].endswith("(specialist)")


def test_audit_records_actions(client, demo):
    run_demo(client, demo["03_bryansk_road_smeta.xlsx"])
    events = client.get("/api/audit").json()
    actions = {e["action"] for e in events}
    assert {"Вход", "Проверка документа"} <= actions
    assert all(e["user"] for e in events)
