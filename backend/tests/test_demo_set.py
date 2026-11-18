"""Тестовый набор с заранее известными отклонениями (demo/expected.json)."""
import json

from conftest import DEMO, run_demo

EXPECTED = {e["file"]: e for e in json.loads((DEMO / "expected.json").read_text(encoding="utf-8"))}


def _levels(item):
    return {s["kind"]: s["level"] for s in item["signals"]}


def test_every_expected_outcome(client, demo):
    for name, exp in EXPECTED.items():
        check = run_demo(client, demo[name])
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
    assert (s["items"], s["matched"], s["high"], s["medium"], s["review"]) == (11, 10, 2, 2, 1)


def test_region_matters(client, demo):
    """Одна и та же спецификация, проверенная по ценам другого региона, даёт другие ориентиры."""
    d = dict(demo["02_tomsk_polyclinic_spec.xlsx"])
    regions = {r["name"]: r for r in client.get("/api/regions").json()}
    other = regions["Брянская область"]
    right = run_demo(client, d)
    wrong = run_demo(client, d | {"region_id": other["id"], "zone_id": other["zones"][0]["id"]})
    bench = lambda c: [next(s["benchmark"] for s in it["signals"] if s["kind"] == "price") for it in c["items"]]
    assert bench(right) != bench(wrong)
    assert right["summary"]["high"] + right["summary"]["medium"] == 2      # только удорожание


def test_real_fgiscs_only(client, demo):
    """Расчёт только по реальным сметным ценам ФГИС ЦС даёт те же сигналы, что и по трём источникам."""
    d = demo["01_bryansk_school_smeta.xlsx"]
    only = run_demo(client, d, sources='["fgiscs"]')
    both = run_demo(client, d)
    levels = lambda c: [[s["level"] for s in it["signals"]] for it in c["items"]]
    assert levels(only) == levels(both)
    first = only["items"][0]["signals"][0]
    assert first["benchmark"] == 6994.01          # сметная цена ФГИС ЦС 04.1.02.05-0184, Брянская обл., III кв. 2026
    assert first["deviation_pct"] == 33.0
