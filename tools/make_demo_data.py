"""Генератор СИНТЕТИЧЕСКИХ источников для демонстрации: контракты-аналоги ЕИС, рыночные
предложения и объекты-аналоги — для ресурсов, которые используются в демо-сметах.

Сметные цены ФГИС ЦС в прототипе реальные (tools/fetch_fgiscs.py). Выгрузить контракты ЕИС и
прайс-листы из рабочей среды прототипа нельзя, поэтому эти два источника и удельные расходы
объектов-аналогов сгенерированы вокруг реальных сметных цен и везде помечены как синтетические.
Реальные выгрузки загружаются через «Справочники цен» в том же формате CSV.

Запуск: python tools/make_demo_data.py → data/reference/demo/{prices,analogs}.csv
Генерация детерминирована (фиксированное зерно).
"""
import csv
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FGIS = ROOT / "data" / "reference" / "fgiscs"
OUT = ROOT / "data" / "reference" / "demo"
SEED = 2026
TAG = {"Брянская область": "БРН", "Томская область": "ТОМ"}

# ресурсы демо-смет: регион → коды КСР
DEMO_RESOURCES = {
    "Брянская область": [
        "04.1.02.05-0184", "04.1.02.05-0003", "08.4.03.03-0032", "05.2.03.17-0004", "12.2.05.10-0037",
        "01.6.01.02-0006", "06.2.05.03-0002", "04.3.01.09-0015", "11.2.02.01-1094", "07.2.06.03-0195",
        "04.2.01.01-0051", "04.2.01.01-1142", "02.2.05.04-2088", "02.3.01.02-1114", "05.2.02.21-0026",
    ],
    "Томская область": [
        "12.2.05.10-0037", "12.2.05.10-0080", "12.2.05.09-0021", "06.2.05.03-0002", "06.1.01.05-0037",
        "21.1.06.07-1347", "21.1.05.01-0017", "12.2.05.09-0102", "24.3.03.11-0071",
    ],
}

# удельный расход на 1 м² объекта-аналога: тип → {код: расход в единицах ресурса}
ANALOG_NORMS = {
    "Школа": {"04.1.02.05-0184": 0.10, "08.4.03.03-0032": 0.009, "05.2.03.17-0004": 0.012,
              "12.2.05.10-0037": 0.045, "01.6.01.02-0006": 1.2, "06.2.05.03-0002": 0.25,
              "04.3.01.09-0015": 0.004, "11.2.02.01-1094": 0.06, "07.2.06.03-0195": 2.4},
    "Поликлиника": {"12.2.05.10-0037": 0.05, "12.2.05.10-0080": 0.012, "12.2.05.09-0021": 0.02,
                    "06.2.05.03-0002": 0.35, "06.1.01.05-0037": 0.014, "21.1.06.07-1347": 0.0009,
                    "21.1.05.01-0017": 0.0006, "12.2.05.09-0102": 0.15, "24.3.03.11-0071": 0.08},
    "Дорога, благоустройство": {"04.2.01.01-0051": 0.12, "04.2.01.01-1142": 0.03, "02.2.05.04-2088": 0.12,
                                "02.3.01.02-1114": 0.15, "05.2.02.21-0026": 0.35},
}
ANALOG_NAMES = {"Школа": "Капитальный ремонт школы на {n} мест",
                "Поликлиника": "Капитальный ремонт поликлиники на {n} посещений в смену",
                "Дорога, благоустройство": "Благоустройство территории и ремонт проездов, участок {n}"}
ANALOG_REGION = {"Школа": ["Брянская область", "Томская область"],
                 "Поликлиника": ["Брянская область", "Томская область"],
                 "Дорога, благоустройство": ["Брянская область", "Томская область"]}


def main() -> None:
    rnd = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    real: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)   # (регион, код) → квартал → цена
    with open(FGIS / "prices.csv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            real[(row["region"], row["ksr_code"])][row["quarter"]] = float(row["price"])

    with open(OUT / "prices.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "ksr_code", "region", "zone", "quarter", "price", "doc_ref", "doc_url"])
        for region, codes in DEMO_RESOURCES.items():
            tag, n_contract, n_offer = TAG[region], 0, 0
            for code in codes:
                series = real[(region, code)]
                assert series, f"{region}: нет реальной цены ФГИС ЦС для {code}"
                quarters = sorted(series)
                for _ in range(5):                      # синтетические контракты-аналоги ЕИС
                    n_contract += 1
                    q = rnd.choice(quarters)
                    p = series[q] * (1 + rnd.uniform(-0.07, 0.07))
                    w.writerow(["eis", code, region, 1, q, f"{p:.2f}",
                                f"Контракт № СИНТ-{tag}-{n_contract:04d} (синтетический), {q}", ""])
                last = quarters[-1]
                for _ in range(3):                      # синтетические рыночные предложения
                    n_offer += 1
                    p = series[last] * (1 + rnd.uniform(-0.05, 0.05))
                    w.writerow(["market", code, region, 1, last, f"{p:.2f}",
                                f"Прайс-лист № СИНТ-{tag}-П{n_offer:03d} (синтетический), {last}", ""])

    with open(OUT / "analogs.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["region", "object_type", "name", "capacity", "ksr_code", "consumption_per_m2", "doc_ref"])
        for otype, norms in ANALOG_NORMS.items():
            for region in ANALOG_REGION[otype]:
                for i in range(4):
                    if otype.startswith("Дорога"):
                        capacity, title = rnd.randrange(2500, 9000, 100), ANALOG_NAMES[otype].format(n=i + 1)
                    else:
                        capacity = rnd.randrange(2800, 6400, 100)
                        title = ANALOG_NAMES[otype].format(n=rnd.choice([300, 400, 550, 600, 825]))
                    ref = f"Объект-аналог СИНТ-{TAG[region]}-{otype[:3].upper()}-{i + 1} (синтетический)"
                    for code, norm in norms.items():
                        w.writerow([region, otype, title, capacity, code,
                                    f"{norm * (1 + rnd.uniform(-0.12, 0.12)):.5f}", ref])
    print("Синтетические источники записаны в", OUT)


if __name__ == "__main__":
    main()
