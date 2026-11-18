from conftest import DEMO, run_demo


def test_89_regions_two_pilots(client):
    regions = client.get("/api/regions").json()
    assert len(regions) == 89
    assert {r["name"] for r in regions if r["is_pilot"]} == {"Брянская область", "Томская область"}
    assert all(r["has_prices"] for r in regions if r["is_pilot"])


def test_signal_card_has_sources_and_formula(client, demo):
    c = run_demo(client, demo["01_bryansk_school_smeta.xlsx"])
    sig = next(s for it in c["items"] for s in it["signals"] if s["level"] == "high" and s["kind"] == "price")
    card = client.get(f"/api/signals/{sig['id']}").json()["signal"]
    srcs = {s["source"]: s for s in card["details"]["sources"]}
    assert set(srcs) == {"fgiscs", "eis", "market"}
    assert srcs["fgiscs"]["synthetic"] is False and srcs["eis"]["synthetic"] and srcs["market"]["synthetic"]
    assert srcs["fgiscs"]["rows"][0]["doc_url"].startswith("https://fgiscs.minstroyrf.ru/")
    assert "×" in card["formula"] and "%" in card["formula"]
    assert all(r["doc_ref"] for s in card["details"]["sources"] for r in s["rows"])


def test_manual_match(client, demo):
    c = run_demo(client, demo["01_bryansk_school_smeta.xlsx"])
    item = next(it for it in c["items"] if not it["match"]["resource"])
    cands = client.get(f"/api/items/{item['id']}/candidates").json()
    assert cands
    r = client.post(f"/api/items/{item['id']}/match", json={"resource_id": cands[0]["id"]})
    assert r.status_code == 200 and r.json()["match"]["method"] == "manual"


def test_report_docx(client, demo):
    c = run_demo(client, demo["02_tomsk_polyclinic_spec.xlsx"])
    r = client.get(f"/api/checks/{c['id']}/report.docx")
    assert r.status_code == 200 and r.content[:2] == b"PK"


def test_rejects_bad_input(client, demo):
    d = demo["01_bryansk_school_smeta.xlsx"]
    base = {"region_id": str(d["region_id"]), "quarter": "2026-Q3"}
    assert client.post("/api/checks", files={"file": ("a.xml", b"<a/>")}, data=base).status_code == 422
    assert client.post("/api/checks", files={"file": ("a.csv", "x;y\n1;2".encode())}, data=base).status_code == 422
    xlsx = (DEMO / d["file"]).read_bytes()
    assert client.post("/api/checks", files={"file": ("a.xlsx", xlsx)},
                       data=base | {"price_thresholds": "[30, 15]"}).status_code == 422


def test_csv_upload_and_reference_import(client, demo):
    d = demo["03_bryansk_road_smeta.xlsx"]
    csv = "Наименование;Ед. изм.;Количество;Цена\nПесок природный для строительных работ II класс, очень мелкий;м3;100;800\nИтого;;;\n".encode()
    r = client.post("/api/checks", files={"file": ("road.csv", csv)}, data={"region_id": str(d["region_id"]), "quarter": "2026-Q2"})
    assert r.status_code == 200
    imp = "source,ksr_code,region,zone,quarter,price,doc_ref\nmarket,02.3.01.02-1114,Брянская область,1,2026-Q3,1000,Тест\n"
    r = client.post("/api/reference/import", data={"kind": "prices"}, files={"file": ("p.csv", imp.encode())})
    assert r.status_code == 200 and r.json()["records"] == 1
    bad = "source,ksr_code,region,quarter,price\nfgiscs,02.3.01.02-1114,Неизвестный край,2026-Q3,10\n"
    r = client.post("/api/reference/import", data={"kind": "prices"}, files={"file": ("b.csv", bad.encode())})
    assert r.status_code == 422 and "Неизвестный край" in r.json()["detail"]
