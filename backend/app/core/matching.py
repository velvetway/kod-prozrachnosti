"""Сопоставление позиции сметы со строительным ресурсом классификатора.

1. Совпадение кода КСР → сопоставимость 1,0.
2. Иначе — нечёткое сравнение нормализованных наименований (rapidfuzz) среди ресурсов
   с совместимой единицей измерения, с проверкой числовых характеристик (класс, диаметр,
   марка): если у ресурса есть число, которого нет в позиции, сопоставимость снижается.
Порядок кандидатов фиксирован: по убыванию показателя, затем по коду ресурса."""
import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from ..config import MATCH_HIGH, MATCH_MEDIUM, MATCH_MIN
from . import units

# латинские и кириллические двойники приводятся к одной записи (B25 = В25, А500С = A500C)
_CONFUSABLES = str.maketrans("abcehkmoptxy", "асеенкмортху")
_STOP = {"для", "и", "с", "в", "на", "из", "по", "класса", "класс", "марки", "марка", "мм", "тип", "типа",
         "диаметр", "диаметром", "толщина", "толщиной", "d", "д", "ф", "гост", "ту", "кг", "м3", "м2"}


@dataclass
class Candidate:
    resource_id: int
    code: str
    name: str
    unit: str
    score: float
    unit_factor: float
    method: str


def level(score: float) -> str:
    if score >= MATCH_HIGH:
        return "Высокая"
    if score >= MATCH_MEDIUM:
        return "Средняя"
    if score >= MATCH_MIN:
        return "Низкая"
    return "Нет"


def _norm(text: str) -> str:
    t = text.lower().replace("ё", "е").translate(_CONFUSABLES)
    t = re.sub(r"(\d),(\d)", r"\1.\2", t)
    t = re.sub(r"[^\w.\s]", " ", t)
    t = re.sub(r"(?<=[^\d\s])(?=\d)|(?<=\d)(?=[^\d\s.])", " ", t)   # «d12мм» → «d 12 мм»
    return t


def _tokens(text: str) -> list[str]:
    out = []
    for tok in _norm(text).split():
        if tok in _STOP:
            continue
        out.append(tok[:6] if not tok[0].isdigit() and len(tok) > 6 else tok)   # грубое отсечение окончаний
    return out


def _numbers(text: str) -> set[str]:
    return {n.rstrip(".") for n in re.findall(r"\d+(?:\.\d+)?", _norm(text))}


def similarity(item_name: str, resource_name: str, resource_attrs: str = "") -> float:
    a, b = " ".join(_tokens(item_name)), " ".join(_tokens(resource_name))
    base = max(fuzz.token_set_ratio(a, b), fuzz.token_sort_ratio(a, b)) / 100
    item_nums, res_nums = _numbers(item_name), _numbers(resource_name + " " + resource_attrs)
    if res_nums and not res_nums <= item_nums:
        missing = len(res_nums - item_nums) / len(res_nums)
        base *= 1 - 0.35 * missing
    return round(base, 4)


def candidates(item_code: str, item_name: str, item_unit: str, resources: list, limit: int = 5) -> list[Candidate]:
    out: list[Candidate] = []
    code = (item_code or "").strip()
    for r in resources:
        f = units.factor(item_unit, r.unit)
        if f is None:
            continue
        if code and code == r.code:
            out.append(Candidate(r.id, r.code, r.name, r.unit, 1.0, f, "code"))
            continue
        out.append(Candidate(r.id, r.code, r.name, r.unit, similarity(item_name, r.name, r.attributes), f, "name"))
    out.sort(key=lambda c: (-c.score, c.code))
    return out[:limit]


def best(item_code: str, item_name: str, item_unit: str, resources: list) -> Candidate | None:
    found = candidates(item_code, item_name, item_unit, resources, limit=1)
    if found and found[0].score >= MATCH_MIN:
        return found[0]
    return None
