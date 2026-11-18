"""Генератор демонстрационных смет с ЗАРАНЕЕ ИЗВЕСТНЫМИ отклонениями (тестовый набор).

Цены позиций задаются как ориентир × коэффициент, поэтому ожидаемый результат проверки
известен заранее и сверяется автотестами (backend/tests/test_demo_set.py).
Запуск после загрузки демо-справочников: python tools/make_demo_files.py → demo/*.xlsx
"""
import json
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core import calc  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import PriceZone, Region, Resource  # noqa: E402
from app.reference.loader import init_db  # noqa: E402

OUT = ROOT / "demo"

# (код в документе, наименование в документе (None — наименование КСР), ед. в документе, количество,
#  код ресурса для расчёта цены, коэффициент к ориентиру, ожидаемый результат)
DOCS = [
    {
        "file": "01_bryansk_school_smeta.xlsx",
        "title": "Локальный сметный расчёт № ДЕМО-1. Капитальный ремонт здания школы. Ведомость материальных ресурсов",
        "region": "Брянская область", "zone": 1, "quarter": "2026-Q3",
        "object_type": "Школа", "capacity": 4200, "base_quarter": None,
        "items": [
            ("04.1.02.05-0184", None, "м3", 420, "04.1.02.05-0184", 1.33, "price:high"),
            ("", "Арматура А-III (А400) диаметр 12 мм, сталь горячекатаная периодического профиля", "кг", 37800,
             "08.4.03.03-0032", 1.06, "price:none; пересчёт кг → т"),
            ("05.2.03.17-0004", None, "1000 шт", 50, "05.2.03.17-0004", 1.02, "price:none"),
            ("", "Плиты теплоизоляционные минераловатные базальтовые, плотность 35-49 кг/м3", "м3", 190,
             "12.2.05.10-0037", 1.22, "price:medium"),
            ("01.6.01.02-0006", None, "м2", 5000, "01.6.01.02-0006", 0.97, "price:none"),
            ("06.2.05.03-0002", None, "м2", 1700, "06.2.05.03-0002", 1.05, "volume:high"),
            ("04.3.01.09-0015", None, "м3", 17, "04.3.01.09-0015", 1.09, "price:none"),
            ("11.2.02.01-1094", None, "м2", 250, "11.2.02.01-1094", 1.20, "price:medium"),
            ("", "Профиль стоечный оцинкованный 50х50, толщина 0,6 мм", "м", 10100, "07.2.06.03-0195", 1.10, "price:none"),
            ("", "Бетон тяжёлый для подготовки, класс В7,5", "м3", 60, "04.1.02.05-0003", 1.36,
             "price:review (низкая сопоставимость)"),
            ("", "Панели фасадные композитные алюминиевые", "м2", 640, None, 4350, "нет ориентира"),
        ],
    },
    {
        "file": "02_tomsk_polyclinic_spec.xlsx",
        "title": "Спецификация ДЕМО-2. Поставка материалов для капитального ремонта поликлиники, изменение цены контракта",
        "region": "Томская область", "zone": 1, "quarter": "2026-Q3",
        "object_type": "Поликлиника", "capacity": 3600, "base_quarter": "2025-Q3",
        "items": [
            ("12.2.05.10-0037", None, "м3", 180, "12.2.05.10-0037", 1.03, "price:none"),
            ("12.2.05.10-0080", None, "м3", 43, "12.2.05.10-0080", 1.02, "price:none"),
            ("12.2.05.09-0021", None, "м3", 72, "12.2.05.09-0021", 1.04, "price:none"),
            ("06.2.05.03-0002", None, "м2", 1260, "06.2.05.03-0002", 1.05, "price:none"),
            ("06.1.01.05-0037", None, "1000 шт", 50, "06.1.01.05-0037", 0.98, "price:none"),
            ("21.1.06.07-1347", None, "1000 м", 3.2, "21.1.06.07-1347", 1.04, "escalation:high"),
            ("21.1.05.01-0017", None, "1000 м", 2.2, "21.1.05.01-0017", 1.01, "price:none"),
            ("12.2.05.09-0102", None, "м2", 540, "12.2.05.09-0102", 1.06, "escalation:medium"),
            ("24.3.03.11-0071", None, "м", 290, "24.3.03.11-0071", 1.00, "price:none"),
        ],
        # исходная цена = цена / (индекс × заявленный сверх индекса рост)
        "escalation": {"21.1.06.07-1347": 1.29, "12.2.05.09-0102": 1.17},
    },
    {
        "file": "03_bryansk_road_smeta.xlsx",
        "title": "Локальный сметный расчёт № ДЕМО-3. Благоустройство территории, ремонт проездов и тротуаров",
        "region": "Брянская область", "zone": 1, "quarter": "2026-Q2",
        "object_type": "Дорога, благоустройство", "capacity": 6000, "base_quarter": None,
        "items": [
            ("04.2.01.01-0051", None, "т", 720, "04.2.01.01-0051", 1.03, "price:none"),
            ("04.2.01.01-1142", None, "т", 180, "04.2.01.01-1142", 0.98, "price:none"),
            ("02.2.05.04-2088", None, "м3", 720, "02.2.05.04-2088", 1.05, "price:none"),
            ("02.3.01.02-1114", None, "м3", 900, "02.3.01.02-1114", 0.96, "price:none"),
            ("05.2.02.21-0026", None, "м2", 2100, "05.2.02.21-0026", 1.02, "price:none"),
        ],
    },
]


def main() -> None:
    init_db()
    OUT.mkdir(exist_ok=True)
    manifest = []
    with SessionLocal() as s:
        for doc in DOCS:
            region = s.scalar(select(Region).where(Region.name == doc["region"]))
            zone = s.scalar(select(PriceZone).where(PriceZone.region_id == region.id,
                                                    PriceZone.number == doc["zone"]))
            idx = calc.IndexBook(s, region.id)
            wb = Workbook()
            ws = wb.active
            ws.title = "Ресурсы"
            ws["A1"] = doc["title"]
            ws["A1"].font = Font(bold=True, size=12)
            ws["A2"] = (f"Демонстрационный (синтетический) документ. {doc['region']}, уровень цен {doc['quarter']}. "
                        f"Цены без НДС. Коды и наименования ресурсов — из КСР (ФГИС ЦС).")
            has_base = bool(doc["base_quarter"])
            header = ["№ п/п", "Код КСР", "Наименование", "Ед. изм.", "Количество", "Цена за ед., руб."]
            if has_base:
                header.append(f"Исходная цена по контракту ({doc['base_quarter']}), руб.")
            header.append("Стоимость, руб.")
            ws.append([])
            ws.append(header)
            for c in ws[4]:
                c.font = Font(bold=True)
                c.alignment = Alignment(wrap_text=True, vertical="top")
            expected = []
            for n, (code, name, unit, qty, res_code, k, exp) in enumerate(doc["items"], start=1):
                if res_code:
                    res = s.scalar(select(Resource).where(Resource.code == res_code))
                    name = name or res.name
                    bm = calc.benchmark(s, res, region.id, zone.id, doc["quarter"], ["fgiscs"], idx)   # от реальной цены
                    from app.core import units
                    f = units.factor(unit, res.unit)
                    price = round(bm.value * k * f, 2)
                else:
                    res, price = None, float(k)
                row = [n, code, name, unit, qty, price]
                if has_base:
                    base = ""
                    if res:
                        coef, info = idx.coef(res, doc["base_quarter"], doc["quarter"])
                        assert info["ok"], f"нет индекса для {res_code}"
                        extra = doc.get("escalation", {}).get(res_code, 1.0)
                        base = round(price / (coef * extra), 2)
                    row.append(base)
                row.append(round(qty * price, 2))
                ws.append(row)
                expected.append({"position": n, "name": name, "resource": res_code, "expected": exp})
            ws.append([])
            ws.append(["", "", "Итого по материалам", "", "", "", ""] if has_base else
                      ["", "", "Итого по материалам", "", "", ""])
            widths = [7, 17, 70, 9, 12, 16, 22, 18]
            for i, w in enumerate(widths[:len(header)]):
                ws.column_dimensions[chr(65 + i)].width = w
            wb.save(OUT / doc["file"])
            manifest.append({k: doc[k] for k in ("file", "title", "region", "zone", "quarter", "object_type",
                                                 "capacity", "base_quarter")} | {"items": expected})
    (OUT / "expected.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Демо-сметы записаны в", OUT)


if __name__ == "__main__":
    main()
