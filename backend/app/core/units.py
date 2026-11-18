"""Единицы измерения: приведение записи к канонической форме и пересчёт между кратными единицами."""
import re

# каноническая запись → (размерность, множитель к базовой единице размерности)
_UNITS = {
    "м3": ("volume", 1), "100 м3": ("volume", 100), "1000 м3": ("volume", 1000),
    "л": ("volume", 0.001),
    "т": ("mass", 1000), "кг": ("mass", 1),
    "м2": ("area", 1), "100 м2": ("area", 100), "1000 м2": ("area", 1000),
    "м": ("length", 1), "100 м": ("length", 100), "1000 м": ("length", 1000), "км": ("length", 1000),
    "шт": ("pieces", 1), "10 шт": ("pieces", 10), "100 шт": ("pieces", 100), "1000 шт": ("pieces", 1000),
    "компл": ("set", 1),
}

_ALIASES = {
    "куб.м": "м3", "куб м": "м3", "м.куб": "м3", "м куб": "м3", "кубм": "м3",
    "кв.м": "м2", "кв м": "м2", "м.кв": "м2", "кв.м.": "м2",
    "тн": "т", "тонна": "т", "тонн": "т", "тн.": "т",
    "килограмм": "кг", "литр": "л",
    "пог.м": "м", "п.м": "м", "пм": "м", "м.п": "м", "метр": "м",
    "штук": "шт", "штука": "шт", "шт.": "шт",
    "тыс.шт": "1000 шт", "тыс шт": "1000 шт", "тыс. шт": "1000 шт",
    "комплект": "компл", "к-т": "компл", "компл.": "компл",
}


def canonical(unit: str) -> str:
    u = (unit or "").strip().lower().replace("³", "3").replace("²", "2").replace(" ", " ")
    u = re.sub(r"\s+", " ", u).rstrip(".")
    if u in _ALIASES:
        return _ALIASES[u]
    m = re.fullmatch(r"(\d+)\s*(.+)", u)
    if m:
        base = canonical(m.group(2))
        return f"{m.group(1)} {base}" if f"{m.group(1)} {base}" in _UNITS else u
    return u


def info(unit: str) -> tuple[str, float] | None:
    return _UNITS.get(canonical(unit))


def factor(item_unit: str, resource_unit: str) -> float | None:
    """Во сколько раз единица позиции больше единицы ресурса.
    Количество в единицах ресурса = количество × factor; цена за единицу ресурса = цена / factor.
    None — единицы несовместимы."""
    a, b = info(item_unit), info(resource_unit)
    if a and b and a[0] == b[0]:
        return a[1] / b[1]
    if canonical(item_unit) == canonical(resource_unit):
        return 1.0
    return None
