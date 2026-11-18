"""Выгрузка РЕАЛЬНЫХ сметных цен строительных материалов с публичного портала ФГИС ЦС
(https://fgiscs.minstroyrf.ru, раздел «Сметные цены строительных ресурсов»).

Для каждого региона и квартала сохраняются:
  data/raw/fgiscs/<регион>_<квартал>.json — ответ портала без изменений (для проверки происхождения);
  data/reference/fgiscs/resources.csv     — ресурсы КСР, встретившиеся в выгрузке;
  data/reference/fgiscs/zones.csv         — ценовые зоны;
  data/reference/fgiscs/prices.csv        — сметные цены (source = fgiscs);
  data/reference/fgiscs/manifest.json     — что, когда и откуда выгружено.

Запуск: python tools/fetch_fgiscs.py [--offline]   (--offline — пересобрать CSV из сохранённых JSON)
"""
import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "fgiscs"
OUT = ROOT / "data" / "reference" / "fgiscs"
API = "https://fgiscs.minstroyrf.ru/api/"
PORTAL = "https://fgiscs.minstroyrf.ru/prices?subjectId={sid}"

REGIONS = {"Брянская область": 269, "Томская область": 307}
QUARTERS = ["2024-Q4", "2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"]


def get(path: str, **params):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"User-Agent": "kod-prozrachnosti-prototype/0.2", "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # временные сбои портала
            if attempt == 2:
                raise
            print("  повтор после ошибки:", e, file=sys.stderr)
            time.sleep(3)


def period_to_quarter(name: str) -> str | None:
    m = re.match(r"(\d)\s*квартал\s*(\d{4})", name)
    return f"{m.group(2)}-Q{m.group(1)}" if m else None


def download() -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    meta = {"source": "ФГИС ЦС, раздел «Сметные цены строительных ресурсов» (материалы)", "api": API,
            "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "files": []}
    subjects = {s["name"]: s["id"] for s in get("EstimatedPrice/CountrySubjects")}
    for region, sid in REGIONS.items():
        assert subjects.get(region) == sid, f"идентификатор субъекта {region} на портале изменился"
        zones = get("EstimatedPrice/PriceZones", subjectId=sid)
        for zone_no, zone in enumerate(zones, start=1):
            periods = {period_to_quarter(p["name"]): p for p in get("EstimatedPrice/Periods", priceZoneId=zone["id"])}
            for q in QUARTERS:
                p = periods.get(q)
                if not p:
                    print(f"{region}: за {q} цен на портале нет")
                    continue
                data = get("EstimatedPrice/BuildingResources/Search/Materials", priceZoneId=zone["id"], periodId=p["id"],
                           countrySubjectId=sid, materials="true")
                fname = f"{sid}_{zone['id']}_{q}.json"
                (RAW / fname).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                n = sum(len(g.get("items", [])) for g in data.get("items", []))
                meta["files"].append({"file": fname, "region": region, "subject_id": sid, "zone_id": zone["id"],
                                      "zone_no": zone_no, "zone_name": zone["name"], "quarter": q,
                                      "period_id": p["id"], "period_name": p["name"], "records": n})
                print(f"{region}, {zone['name']}, {p['name']}: {n} материалов")
                time.sleep(0.5)
    (RAW / "manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def group_of(code: str) -> str:
    return "Раздел КСР " + ".".join(code.split("-")[0].split(".")[:3])


def build(meta: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    resources: dict[str, dict] = {}
    prices: list[list] = []
    by_region: dict[str, dict[str, dict[str, float]]] = {}
    zones = set()
    for f in meta["files"]:
        data = json.loads((RAW / f["file"]).read_text(encoding="utf-8"))
        zones.add((f["region"], f["zone_no"], f"Ценовая зона «{f['zone_name']}» (ФГИС ЦС)"))
        for g in data.get("items", []):
            for it in g.get("items", []):
                code = it["code"].strip()
                price = float(it["estimatedPrice"])
                resources[code] = {"ksr_code": code, "name": it["name"].strip(), "unit": it["unitName"].strip(),
                                   "group": group_of(code), "attributes": ""}
                prices.append(["fgiscs", code, f["region"], f["zone_no"], f["quarter"], f"{price:.2f}",
                               f"ФГИС ЦС, сметная цена {code}, {f['region']}, {f['period_name']}",
                               PORTAL.format(sid=f["subject_id"])])
                by_region.setdefault(f["region"], {}).setdefault(f["quarter"], {})[code] = price

    with open(OUT / "resources.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["ksr_code", "name", "unit", "group", "attributes"])
        w.writeheader()
        for code in sorted(resources):
            w.writerow(resources[code])
    with open(OUT / "zones.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["region", "zone", "name"])
        w.writerows(sorted(zones))
    with open(OUT / "prices.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "ksr_code", "region", "zone", "quarter", "price", "doc_ref", "doc_url"])
        w.writerows(prices)

    manifest = dict(meta)
    manifest.update({"resources": len(resources), "prices": len(prices)})
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Ресурсов: {len(resources)}, цен: {len(prices)} → {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="не обращаться к порталу, собрать CSV из data/raw")
    args = ap.parse_args()
    meta = json.loads((RAW / "manifest.json").read_text(encoding="utf-8")) if args.offline else download()
    build(meta)
