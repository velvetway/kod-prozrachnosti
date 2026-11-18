"""Генератор ДЕМОНСТРАЦИОННОГО набора справочников для Брянской и Томской областей.

Все цены, индексы, контракты и объекты-аналоги здесь синтетические: они нужны, чтобы
показать работу прототипа. Реальные выгрузки ФГИС ЦС, ЕИС и прайс-листов загружаются
через раздел «Справочники» (или API /api/reference/import) в том же формате CSV.

Запуск: python tools/make_demo_data.py  → data/reference/demo/*.csv
Генерация детерминирована (фиксированное зерно), повторный запуск даёт те же файлы.
"""
import csv
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "reference" / "demo"
SEED = 2026

QUARTERS = ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3", "2026-Q4"]
BASE_Q = "2026-Q3"   # квартал, к которому привязаны базовые цены ниже

# код, наименование, единица, группа, характеристики, базовая цена (руб. без НДС, Брянская обл., 2026-Q3)
RESOURCES = [
    ("Д01.01", "Бетон тяжёлый, класс B15 (М200)", "м3", "Бетон и растворы", "B15", 6200),
    ("Д01.02", "Бетон тяжёлый, класс B25 (М350)", "м3", "Бетон и растворы", "B25", 7420),
    ("Д01.03", "Раствор кладочный цементный М150", "м3", "Бетон и растворы", "М150", 5600),
    ("Д02.01", "Арматура А500С, диаметр 12 мм", "т", "Металлопрокат", "А500С d12", 71200),
    ("Д02.02", "Арматура А500С, диаметр 16 мм", "т", "Металлопрокат", "А500С d16", 69800),
    ("Д03.01", "Кирпич керамический рядовой полнотелый М150", "1000 шт", "Стеновые материалы", "М150", 20900),
    ("Д03.02", "Блоки из ячеистого бетона D500, 600×300×200 мм", "м3", "Стеновые материалы", "D500", 6100),
    ("Д04.01", "Цемент ЦЕМ I 42,5Н (М500)", "т", "Вяжущие и нерудные", "42,5Н", 7900),
    ("Д04.02", "Песок строительный для строительных работ", "м3", "Вяжущие и нерудные", "", 780),
    ("Д04.03", "Щебень гранитный фракции 20–40 мм", "м3", "Вяжущие и нерудные", "20-40", 2150),
    ("Д05.01", "Плиты минераловатные теплоизоляционные, плотность 125 кг/м3", "м3", "Изоляция", "125 кг/м3", 5650),
    ("Д06.01", "Профилированный лист С21 с полимерным покрытием, толщина 0,6 мм", "м2", "Кровля и фасад", "С21 0,6", 640),
    ("Д06.02", "Мембрана кровельная ПВХ, толщина 1,5 мм", "м2", "Кровля и фасад", "1,5", 590),
    ("Д07.01", "Листы гипсокартонные ГКЛ 12,5 мм", "м2", "Отделочные материалы", "12,5", 205),
    ("Д07.02", "Плитка керамическая для полов", "м2", "Отделочные материалы", "", 890),
    ("Д07.03", "Линолеум коммерческий гетерогенный", "м2", "Отделочные материалы", "", 980),
    ("Д07.04", "Краска водно-дисперсионная для внутренних работ", "кг", "Отделочные материалы", "", 210),
    ("Д08.01", "Кабель силовой ВВГнг(А)-LS 3×2,5", "м", "Инженерные системы", "3×2,5", 98),
    ("Д08.02", "Трубы напорные полиэтиленовые ПЭ100 SDR17, диаметр 110 мм", "м", "Инженерные системы", "110", 690),
    ("Д08.03", "Блок оконный ПВХ с двухкамерным стеклопакетом", "м2", "Окна и двери", "", 7800),
    ("Д09.01", "Смесь асфальтобетонная горячая плотная, тип Б", "т", "Дорожные материалы", "тип Б", 6900),
    ("Д09.02", "Камень бортовой бетонный БР 100.30.15", "шт", "Дорожные материалы", "БР 100.30.15", 520),
]

# рост цен группы за квартал (демо)
GROUP_GROWTH = {
    "Бетон и растворы": 0.016, "Металлопрокат": 0.008, "Стеновые материалы": 0.014,
    "Вяжущие и нерудные": 0.012, "Изоляция": 0.015, "Кровля и фасад": 0.011,
    "Отделочные материалы": 0.013, "Инженерные системы": 0.020, "Окна и двери": 0.012,
    "Дорожные материалы": 0.017,
}

# регион → [(номер зоны, название, коэффициент к базовой цене)]
ZONES = {
    "Брянская область": [(1, "Ценовая зона 1 (демо): г. Брянск и районы области", 1.00)],
    "Томская область": [
        (1, "Ценовая зона 1 (демо): г. Томск и прилегающие районы", 1.07),
        (2, "Ценовая зона 2 (демо): северные районы с сезонным завозом", 1.32),
    ],
}
REGION_TAG = {"Брянская область": "БРН", "Томская область": "ТОМ"}

# удельный расход на 1 м² объекта-аналога: тип → {код: расход}
ANALOG_NORMS = {
    "Школа": {"Д01.02": 0.10, "Д02.01": 0.009, "Д03.01": 0.012, "Д05.01": 0.045, "Д07.01": 1.2,
              "Д07.02": 0.25, "Д07.03": 0.55, "Д07.04": 0.9, "Д08.01": 6.0, "Д08.03": 0.12},
    "Поликлиника": {"Д01.02": 0.11, "Д02.01": 0.010, "Д03.02": 0.08, "Д05.01": 0.05, "Д07.01": 1.4,
                    "Д07.02": 0.35, "Д07.03": 0.5, "Д07.04": 1.0, "Д08.01": 9.0, "Д08.03": 0.11},
    "Дорога, благоустройство": {"Д09.01": 0.14, "Д09.02": 0.08, "Д04.03": 0.12, "Д04.02": 0.15},
}
ANALOG_NAMES = {
    "Школа": ["Капитальный ремонт школы на {n} мест", 4],
    "Поликлиника": ["Капитальный ремонт поликлиники на {n} посещений в смену", 4],
    "Дорога, благоустройство": ["Благоустройство территории и ремонт проездов, участок {n}", 4],
}


def index_value(group: str, quarter: str, region: str) -> float:
    g = GROUP_GROWTH[group] + (0.002 if region == "Томская область" else 0.0)
    return round((1 + g) ** QUARTERS.index(quarter), 4)


def price_at(base: float, group: str, quarter: str, region: str, zone_k: float) -> float:
    k = index_value(group, quarter, region) / index_value(group, BASE_Q, region)
    return base * k * zone_k


def main() -> None:
    rnd = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)

    with open(OUT / "resources.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ksr_code", "name", "unit", "group", "attributes"])
        for code, name, unit, group, attrs, _ in RESOURCES:
            w.writerow([code, name, unit, group, attrs])

    with open(OUT / "zones.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["region", "zone", "name"])
        for region, zones in ZONES.items():
            for num, name, _ in zones:
                w.writerow([region, num, name])

    with open(OUT / "indexes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["region", "group", "quarter", "value"])
        for region in ZONES:
            for group in GROUP_GROWTH:
                for q in QUARTERS:
                    w.writerow([region, group, q, f"{index_value(group, q, region):.4f}"])

    with open(OUT / "prices.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "ksr_code", "region", "zone", "quarter", "price", "doc_ref", "doc_url"])
        for region, zones in ZONES.items():
            tag = REGION_TAG[region]
            contract_no = 0
            offer_no = 0
            for num, _, zk in zones:
                zone_k = zk
                for code, name, unit, group, _, base in RESOURCES:
                    # ФГИС ЦС: сметная цена на каждый квартал 2026 года
                    for q in QUARTERS[4:]:
                        p = price_at(base, group, q, region, zone_k)
                        w.writerow(["fgiscs", code, region, num, q, f"{p:.2f}",
                                    f"ФГИС ЦС, сметная цена ресурса {code}, {q} (демо)", ""])
                    # ЕИС: контракты-аналоги за прошлые кварталы
                    for _ in range(5 if num == 1 else 3):
                        contract_no += 1
                        q = rnd.choice(QUARTERS[1:7])
                        p = price_at(base, group, q, region, zone_k) * (1 + rnd.uniform(-0.07, 0.07))
                        w.writerow(["eis", code, region, num, q, f"{p:.2f}",
                                    f"Контракт № ДЕМО-{tag}-{contract_no:04d}, {q}", ""])
                    # Рыночные предложения: прайс-листы ноября 2026
                    for _ in range(3):
                        offer_no += 1
                        p = price_at(base, group, "2026-Q4", region, zone_k) * (1 + rnd.uniform(-0.05, 0.05))
                        w.writerow(["market", code, region, num, "2026-Q4", f"{p:.2f}",
                                    f"Прайс-лист поставщика № ДЕМО-{tag}-П{offer_no:03d}, ноябрь 2026", ""])

    with open(OUT / "analogs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["region", "object_type", "name", "capacity", "ksr_code", "consumption_per_m2", "doc_ref"])
        for region in ZONES:
            tag = REGION_TAG[region]
            for otype, norms in ANALOG_NORMS.items():
                template, count = ANALOG_NAMES[otype]
                for i in range(count):
                    if otype == "Дорога, благоустройство":
                        capacity = rnd.randrange(2500, 9000, 100)
                        title = template.format(n=i + 1)
                    else:
                        capacity = rnd.randrange(2800, 6400, 100)
                        title = template.format(n=rnd.choice([300, 400, 550, 600, 825]))
                    ref = f"Объект-аналог ДЕМО-{tag}-{otype[:3].upper()}-{i + 1}"
                    for code, norm in norms.items():
                        value = norm * (1 + rnd.uniform(-0.12, 0.12))
                        w.writerow([region, otype, title, capacity, code, f"{value:.4f}", ref])

    print("Демо-справочники записаны в", OUT)


if __name__ == "__main__":
    main()
