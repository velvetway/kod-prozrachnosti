"""Сопоставление позиции сметы со строительным ресурсом классификатора.

1. Совпадение кода КСР → сопоставимость 1,0.
2. Иначе — нечёткое сравнение нормализованных наименований (rapidfuzz) среди ресурсов
   с совместимой единицей измерения, с проверкой числовых характеристик (класс, диаметр,
   марка): если у ресурса есть число, которого нет в позиции, сопоставимость снижается.
Порядок кандидатов фиксирован: по убыванию показателя, затем по коду ресурса."""
import re
from dataclasses import dataclass
from functools import lru_cache

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


@lru_cache(maxsize=50000)
def _norm(text: str) -> str:
    t = text.lower().replace("ё", "е").translate(_CONFUSABLES)
    t = re.sub(r"(\d),(\d)", r"\1.\2", t)
    t = re.sub(r"[^\w.\s]", " ", t)
    t = re.sub(r"(?<=[^\d\s])(?=\d)|(?<=\d)(?=[^\d\s.])", " ", t)   # «d12мм» → «d 12 мм»
    return t


@lru_cache(maxsize=50000)
def _joined_tokens(text: str) -> str:
    return " ".join(_tokens(text))


def _tokens(text: str) -> list[str]:
    out = []
    for tok in _norm(text).split():
        if tok in _STOP:
            continue
        out.append(tok[:5] if not tok[0].isdigit() and len(tok) > 5 else tok)   # грубое отсечение окончаний
    return out


@lru_cache(maxsize=50000)
def _numbers(text: str) -> frozenset[str]:
    return frozenset(n.rstrip(".") for n in re.findall(r"\d+(?:\.\d+)?", _norm(text)))


def similarity(item_name: str, resource_name: str, resource_attrs: str = "") -> float:
    a, b = _joined_tokens(item_name), _joined_tokens(resource_name)
    base = max(fuzz.token_set_ratio(a, b), fuzz.token_sort_ratio(a, b)) / 100
    item_nums, res_nums = _numbers(item_name), _numbers(resource_name + " " + resource_attrs)
    if res_nums and not res_nums <= item_nums:          # у ресурса есть характеристика, которой нет в позиции
        base *= 1 - 0.35 * len(res_nums - item_nums) / len(res_nums)
    if item_nums and not item_nums <= res_nums:          # у позиции есть характеристика, которой нет у ресурса
        base *= 1 - 0.15 * len(item_nums - res_nums) / len(item_nums)
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
    out.sort(key=lambda c: (-c.score, c.method != "code", c.code))
    return out[:limit]


def best(item_code: str, item_name: str, item_unit: str, resources: list) -> Candidate | None:
    found = candidates(item_code, item_name, item_unit, resources, limit=1)
    if found and found[0].score >= MATCH_MIN:
        return found[0]
    return None
