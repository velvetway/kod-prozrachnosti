"""Извлечение позиций из сметы или спецификации (XLSX, CSV).

Строка заголовка ищется по ключевым словам в первых 40 строках; строки разделов, итогов
и строки без числовых количества или цены пропускаются с предупреждением."""
import csv
import io
import re
from dataclasses import dataclass, field

from openpyxl import load_workbook

COLUMN_KEYS = {
    "base_price": ["исходная цена", "цена по контракту", "базовая цена", "цена до изменения"],
    "code": ["код кср", "код ресурса", "шифр", "код"],
    "name": ["наименование"],
    "unit": ["ед. изм", "ед.изм", "единица", "ед."],
    "quantity": ["количество", "кол-во", "кол.", "объем", "объём"],
    "price": ["цена за ед", "цена", "стоимость единицы"],
}
COLUMN_EXCLUDE = {"unit": ("цена", "стоимость"), "code": ("кол",), "price": ("исходн", "контракт")}
SKIP_WORDS = ("итого", "всего", "раздел", "ндс", "накладные", "сметная прибыль")


class ParseError(ValueError):
    pass


@dataclass
class ParsedItem:
    row: int
    code: str
    name: str
    unit: str
    quantity: float
    price: float
    base_price: float | None = None


@dataclass
class ParsedDoc:
    title: str
    items: list[ParsedItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    has_base_price: bool = False


def _text(v) -> str:
    return "" if v is None else re.sub(r"\s+", " ", str(v)).strip()


def _number(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _map_header(cells: list[str]) -> dict[str, int] | None:
    low = [c.lower() for c in cells]
    found: dict[str, int] = {}
    for key, variants in COLUMN_KEYS.items():          # порядок важен: «исходная цена» раньше «цены»
        for i, c in enumerate(low):
            if i in found.values() or not c:
                continue
            if any(x in c for x in COLUMN_EXCLUDE.get(key, ())):
                continue
            if any(v in c for v in variants):
                found[key] = i
                break
    return found if {"name", "unit", "quantity", "price"} <= found.keys() else None


def _parse_rows(rows: list[list], default_title: str) -> ParsedDoc:
    header_idx, cols = None, None
    for i, row in enumerate(rows[:40]):
        cols = _map_header([_text(c) for c in row])
        if cols:
            header_idx = i
            break
    if cols is None:
        raise ParseError("Не найдена строка заголовка: нужны колонки «Наименование», «Ед. изм.», "
                         "«Количество» и «Цена»")
    title = next((_text(c) for r in rows[:header_idx] for c in r if len(_text(c)) > 12), default_title)
    doc = ParsedDoc(title=title, has_base_price="base_price" in cols)
    for i, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        get = lambda k: row[cols[k]] if k in cols and cols[k] < len(row) else None
        name = _text(get("name"))
        if not name:
            continue
        if any(name.lower().startswith(w) for w in SKIP_WORDS):
            continue
        qty, price = _number(get("quantity")), _number(get("price"))
        if qty is None or price is None or qty <= 0 or price <= 0:
            doc.warnings.append(f"Строка {i}: «{name[:60]}» пропущена — нет числового количества или цены")
            continue
        doc.items.append(ParsedItem(row=i, code=_text(get("code")), name=name, unit=_text(get("unit")),
                                    quantity=qty, price=price, base_price=_number(get("base_price"))))
    if not doc.items:
        raise ParseError("В документе не найдено ни одной позиции с количеством и ценой")
    return doc


def parse(data: bytes, file_name: str) -> ParsedDoc:
    ext = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    stem = file_name.rsplit(".", 1)[0]
    if ext == "xlsx":
        try:
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as e:  # повреждённый файл
            raise ParseError(f"Не удалось открыть XLSX: {e}")
        ws = wb.worksheets[0]
        return _parse_rows([list(r) for r in ws.iter_rows(values_only=True)], stem)
    if ext == "csv":
        text = data.decode("utf-8-sig", errors="replace")
        delim = ";" if text[:2000].count(";") > text[:2000].count(",") else ","
        return _parse_rows(list(csv.reader(io.StringIO(text), delimiter=delim)), stem)
    if ext == "xml":
        raise ParseError("XML локального сметного расчёта будет поддержан в следующей версии; "
                         "сохраните смету в XLSX")
    raise ParseError("Поддерживаются файлы XLSX и CSV")
