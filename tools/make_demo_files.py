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

# (код в документе, наименование в документе, ед. в документе, количество, код ресурса для расчёта цены,
#  коэффициент к ориентиру, ожидаемый результат)
DOCS = [
    {
        "file": "01_bryansk_school_smeta.xlsx",
        "title": "Локальный сметный расчёт № ДЕМО-1. Капитальный ремонт здания школы. Ведомость материальных ресурсов",
        "region": "Брянская область", "zone": 1, "quarter": "2026-Q3",
        "object_type": "Школа", "capacity": 4200, "base_quarter": None,
        "items": [
            ("Д01.02", "Бетон тяжёлый, класс B25 (М350)", "м3", 420, "Д01.02", 1.33, "price:high"),
            ("", "Арматурная сталь класса А500С d=12мм", "кг", 37800, "Д02.01", 1.06, "price:none; конверсия кг→т"),
            ("Д03.01", "Кирпич керамический рядовой полнотелый М150", "1000 шт", 50, "Д03.01", 1.02, "price:none"),
            ("", "Плиты теплоизоляционные из минеральной ваты 125кг/м3", "м3", 190, "Д05.01", 1.22, "price:medium"),
            ("Д07.01", "Листы гипсокартонные ГКЛ 12,5 мм", "м2", 5000, "Д07.01", 0.97, "price:none"),
            ("Д07.02", "Плитка керамическая для полов", "м2", 1050, "Д07.02", 1.04, "price:none"),
            ("", "Линолеум гетерогенный коммерческий", "м2", 4100, "Д07.03", 1.05, "volume:high"),
            ("Д07.04", "Краска водно-дисперсионная для внутренних работ", "кг", 3900, "Д07.04", 1.09, "price:none"),
            ("", "Кабель ВВГнг-LS 3x2.5", "м", 25500, "Д08.01", 1.12, "price:none"),
            ("Д08.03", "Блок оконный ПВХ с двухкамерным стеклопакетом", "м2", 510, "Д08.03", 1.17, "price:medium"),
            ("", "Бетон тяжёлый для подготовки, класс В15", "м3", 60, "Д01.01", 1.36, "price:review (низкая сопоставимость)"),
            ("", "Панели фасадные композитные алюминиевые", "м2", 640, None, 4350, "нет ориентира"),
        ],
    },
    {
        "file": "02_tomsk_polyclinic_spec.xlsx",
        "title": "Спецификация ДЕМО-2. Поставка строительных материалов для капитального ремонта поликлиники (северный район)",
        "region": "Томская область", "zone": 2, "quarter": "2026-Q3",
        "object_type": "Поликлиника", "capacity": 3600, "base_quarter": "2025-Q4",
        "items": [
            ("Д01.02", "Бетон тяжёлый, класс B25 (М350)", "м3", 400, "Д01.02", 1.04, "price:none (цена зоны 2)"),
            ("Д02.02", "Арматура А500С, диаметр 16 мм", "т", 36, "Д02.02", 1.02, "price:none"),
            ("Д03.02", "Блоки из ячеистого бетона D500, 600×300×200 мм", "м3", 290, "Д03.02", 1.06, "price:none"),
            ("Д05.01", "Плиты минераловатные теплоизоляционные, плотность 125 кг/м3", "м3", 180, "Д05.01", 1.03, "price:none"),
            ("Д07.01", "Листы гипсокартонные ГКЛ 12,5 мм", "м2", 5000, "Д07.01", 0.99, "price:none"),
            ("Д07.02", "Плитка керамическая для полов", "м2", 1260, "Д07.02", 1.05, "price:none"),
            ("Д07.03", "Линолеум коммерческий гетерогенный", "м2", 1800, "Д07.03", 1.01, "price:none"),
            ("Д07.04", "Краска водно-дисперсионная для внутренних работ", "кг", 3600, "Д07.04", 1.00, "price:none"),
            ("Д08.01", "Кабель силовой ВВГнг(А)-LS 3×2,5", "м", 32400, "Д08.01", 1.08, "escalation:high"),
            ("Д08.03", "Блок оконный ПВХ с двухкамерным стеклопакетом", "м2", 400, "Д08.03", 1.06, "escalation:medium"),
        ],
        # исходная цена = цена / (индекс × заявленный сверх индекса рост)
        "escalation": {"Д08.01": 1.29, "Д08.03": 1.17},
    },
    {
        "file": "03_bryansk_road_smeta.xlsx",
        "title": "Локальный сметный расчёт № ДЕМО-3. Благоустройство территории, ремонт проездов и тротуаров",
        "region": "Брянская область", "zone": 1, "quarter": "2026-Q2",
        "object_type": "Дорога, благоустройство", "capacity": 6000, "base_quarter": None,
        "items": [
            ("Д09.01", "Смесь асфальтобетонная горячая плотная, тип Б", "т", 840, "Д09.01", 1.03, "price:none"),
            ("Д09.02", "Камень бортовой бетонный БР 100.30.15", "шт", 480, "Д09.02", 0.98, "price:none"),
            ("Д04.03", "Щебень гранитный фракции 20–40 мм", "м3", 720, "Д04.03", 1.05, "price:none"),
            ("Д04.02", "Песок строительный для строительных работ", "м3", 900, "Д04.02", 0.96, "price:none"),
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
            ws["A2"] = (f"Демонстрационный документ. {doc['region']}, уровень цен {doc['quarter']}. "
                        f"Цены без НДС.")
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
                    bm = calc.benchmark(s, res, region.id, zone.id, doc["quarter"], ["fgiscs", "eis", "market"], idx)
                    from app.core import units
                    f = units.factor(unit, res.unit)
                    price = round(bm.value * k * f, 2)
                else:
                    res, price = None, float(k)
                row = [n, code, name, unit, qty, price]
                if has_base:
                    base = ""
                    if res:
                        coef, _ = idx.coef(res.group, doc["base_quarter"], doc["quarter"])
                        extra = doc.get("escalation", {}).get(res_code, 1.0)
                        base = round(price / (coef * extra), 2)
                    row.append(base)
                row.append(round(qty * price, 2))
                ws.append(row)
                expected.append({"position": n, "name": name, "expected": exp})
            ws.append([])
            ws.append(["", "", "Итого по материалам", "", "", "", ""] if has_base else
                      ["", "", "Итого по материалам", "", "", ""])
            widths = [7, 10, 58, 9, 12, 16, 22, 18]
            for i, w in enumerate(widths[:len(header)]):
                ws.column_dimensions[chr(65 + i)].width = w
            wb.save(OUT / doc["file"])
            manifest.append({k: doc[k] for k in ("file", "title", "region", "zone", "quarter", "object_type",
                                                 "capacity", "base_quarter")} | {"items": expected})
    (OUT / "expected.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Демо-сметы записаны в", OUT)


if __name__ == "__main__":
    main()
