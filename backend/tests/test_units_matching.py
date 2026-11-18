from types import SimpleNamespace as R

import pytest

from app.core import matching, units


@pytest.mark.parametrize("item,res,expected", [
    ("кг", "т", 0.001), ("т", "т", 1.0), ("тыс.шт", "1000 шт", 1.0), ("шт", "1000 шт", 0.001),
    ("куб.м", "м3", 1.0), ("м³", "м3", 1.0), ("кв.м", "м2", 1.0), ("100 м", "м", 100.0),
])
def test_unit_factor(item, res, expected):
    assert units.factor(item, res) == pytest.approx(expected)


def test_incompatible_units():
    assert units.factor("м3", "т") is None
    assert units.factor("шт", "м2") is None


RES = [
    R(id=1, code="Д01.01", name="Бетон тяжёлый, класс B15 (М200)", unit="м3", attributes="B15"),
    R(id=2, code="Д01.02", name="Бетон тяжёлый, класс B25 (М350)", unit="м3", attributes="B25"),
    R(id=3, code="Д02.01", name="Арматура А500С, диаметр 12 мм", unit="т", attributes="А500С d12"),
    R(id=4, code="Д02.02", name="Арматура А500С, диаметр 16 мм", unit="т", attributes="А500С d16"),
]


def test_code_match_wins():
    c = matching.best("Д01.02", "что угодно", "м3", RES)
    assert c.code == "Д01.02" and c.score == 1.0 and c.method == "code"


def test_latin_cyrillic_and_numbers():
    # латинская B и кириллическая В, класс должен совпасть
    assert matching.best("", "Бетон В25 (М350) тяжёлый", "м3", RES).code == "Д01.02"
    # диаметр отличает 12 от 16, единица кг пересчитывается в т
    c = matching.best("", "Арматурная сталь класса А500С d=12мм", "кг", RES)
    assert c.code == "Д02.01" and c.unit_factor == pytest.approx(0.001)


def test_unit_filter_and_threshold():
    assert matching.best("", "Бетон тяжёлый B25", "т", RES) is None          # несовместимая единица
    assert matching.best("", "Панели фасадные композитные", "м3", RES) is None  # ниже порога


def test_order_is_deterministic():
    a = matching.candidates("", "Арматура А500С", "т", RES)
    b = matching.candidates("", "Арматура А500С", "т", list(reversed(RES)))
    assert [x.code for x in a] == [x.code for x in b]
