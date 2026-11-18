"""Тестовый набор с заранее известными отклонениями (demo/expected.json)."""
import json

from conftest import DEMO, run_demo

EXPECTED = {e["file"]: e for e in json.loads((DEMO / "expected.json").read_text(encoding="utf-8"))}


def _levels(item):
    return {s["kind"]: s["level"] for s in item["signals"]}


def test_every_expected_outcome(client, demo):
    for name, exp in EXPECTED.items():
        check = run_demo(client, demo[name])
        assert check["is_demo"]
        for item, e in zip(check["items"], exp["items"]):
            want = e["expected"]
            got = _levels(item)
            if want == "нет ориентира":
                assert got == {"price": "nomatch"}, (name, item["name"], got)
                continue
            kind, level = want.split(";")[0].split(" ")[0].split(":")
            assert got.get(kind) == level, (name, item["name"], want, got)
            # остальные виды контроля по позиции без сигналов
            for k, v in got.items():
                if k != kind:
                    assert v == "none", (name, item["name"], k, v)


def test_school_summary(client, demo):
    s = run_demo(client, demo["01_bryansk_school_smeta.xlsx"])["summary"]
    assert (s["items"], s["matched"], s["high"], s["medium"], s["review"]) == (12, 11, 2, 2, 1)


def test_zone_matters(client, demo):
    """Те же цены северного района Томской области дают сигналы, если сравнить их с зоной 1."""
    d = dict(demo["02_tomsk_polyclinic_spec.xlsx"])
    regions = {r["id"]: r for r in client.get("/api/regions").json()}
    zone1 = regions[d["region_id"]]["zones"][0]["id"]
    assert zone1 != d["zone_id"]
    right = run_demo(client, d)
    wrong = run_demo(client, d | {"zone_id": zone1})
    price = lambda c: [s["level"] for it in c["items"] for s in it["signals"] if s["kind"] == "price"]
    assert set(price(right)) == {"none"}
    assert "none" not in price(wrong)          # ~ +23 %: каждая позиция получает сигнал


def test_disabled_source_changes_benchmark(client, demo):
    d = demo["01_bryansk_school_smeta.xlsx"]
    only = run_demo(client, d, sources='["fgiscs"]')
    first = only["items"][0]["signals"][0]
    assert first["benchmark"] == 7420.0          # демо-сметная цена ФГИС ЦС на III кв. 2026
