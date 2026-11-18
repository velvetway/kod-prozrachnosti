"""Расчёт ориентиров и отклонений. Только правила и статистика, без случайных величин.

Ориентир цены = медиана значений трёх источников, приведённых к кварталу проверки индексом
цен группы ресурсов:
  • ФГИС ЦС — сметная цена для ценовой зоны (ближайший квартал, проиндексированный);
  • ЕИС — медиана цен контрактов-аналогов, каждая проиндексирована к кварталу проверки;
  • рынок — медиана цен открытых предложений, проиндексированных к кварталу проверки.
"""
from dataclasses import dataclass, field
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AnalogObject, PriceIndex, ReferencePrice, Resource

SOURCE_TITLES = {"fgiscs": "ФГИС ЦС", "eis": "Контракты-аналоги ЕИС", "market": "Рыночные предложения"}


def q_key(q: str) -> tuple[int, int]:
    year, quarter = q.split("-Q")
    return int(year), int(quarter)


@dataclass
class SourceValue:
    source: str
    value: float
    rows: list[dict] = field(default_factory=list)
    note: str = ""


@dataclass
class Benchmark:
    value: float | None
    sources: list[SourceValue]
    notes: list[str]


class IndexBook:
    """Индексы цен региона; при отсутствии значения коэффициент = 1 с пометкой."""

    def __init__(self, s: Session, region_id: int):
        self.values: dict[tuple[str, str], float] = {
            (p.group, p.quarter): p.value
            for p in s.scalars(select(PriceIndex).where(PriceIndex.region_id == region_id))
        }

    def coef(self, group: str, from_q: str, to_q: str) -> tuple[float, bool]:
        a, b = self.values.get((group, from_q)), self.values.get((group, to_q))
        if not a or not b:
            return 1.0, False
        return b / a, True


def benchmark(s: Session, resource: Resource, region_id: int, zone_id: int | None, quarter: str,
              sources: list[str], idx: IndexBook) -> Benchmark:
    rows = list(s.scalars(
        select(ReferencePrice).where(ReferencePrice.resource_id == resource.id,
                                     ReferencePrice.region_id == region_id)
        .order_by(ReferencePrice.source, ReferencePrice.quarter, ReferencePrice.id)))
    notes: list[str] = []
    zone_rows = [r for r in rows if r.zone_id == zone_id] if zone_id else rows
    if zone_id and not zone_rows and rows:
        notes.append("Для выбранной ценовой зоны цен нет — использованы цены других зон региона")
        zone_rows = rows
    out: list[SourceValue] = []
    for src in ("fgiscs", "eis", "market"):
        if src not in sources:
            continue
        src_rows = [r for r in zone_rows if r.source == src]
        if not src_rows:
            continue
        if src == "fgiscs":
            exact = [r for r in src_rows if r.quarter == quarter]
            if exact:
                chosen = [exact[0]]
            else:
                earlier = [r for r in src_rows if q_key(r.quarter) <= q_key(quarter)]
                chosen = [(earlier or src_rows)[-1] if earlier else src_rows[0]]
        else:
            chosen = src_rows
        detail, values, missing_index = [], [], False
        for r in chosen:
            k, ok = idx.coef(resource.group, r.quarter, quarter)
            missing_index |= not ok
            v = r.price * k
            values.append(v)
            detail.append({"doc_ref": r.doc_ref, "doc_url": r.doc_url, "quarter": r.quarter,
                           "price": round(r.price, 2), "index": round(k, 4), "indexed": round(v, 2)})
        note = "нет индекса для пересчёта — цена взята без индексации" if missing_index else ""
        out.append(SourceValue(src, round(median(values), 2), detail, note))
    value = round(median([sv.value for sv in out]), 2) if out else None
    if not out:
        notes.append("Ни в одном источнике нет цены этого ресурса для региона")
    return Benchmark(value, out, notes)


def classify(dev: float, thresholds: tuple[float, float]) -> str:
    medium, high = thresholds
    if dev >= high:
        return "high"
    if dev >= medium:
        return "medium"
    return "none"


@dataclass
class VolumeNorm:
    median: float
    low: float
    high: float
    count: int
    scope: str
    analogs: list[dict]


def volume_norm(s: Session, resource_code: str, region_id: int, object_type: str) -> VolumeNorm | None:
    def collect(objs):
        return [(o, o.consumption[resource_code]) for o in objs if resource_code in (o.consumption or {})]

    base = select(AnalogObject).where(AnalogObject.object_type == object_type).order_by(AnalogObject.id)
    found = collect(s.scalars(base.where(AnalogObject.region_id == region_id)))
    scope = "объекты-аналоги региона"
    if len(found) < 3:
        found = collect(s.scalars(base))
        scope = "объекты-аналоги всех регионов (в регионе меньше трёх)"
    if len(found) < 3:
        return None
    vals = [v for _, v in found]
    return VolumeNorm(round(median(vals), 4), round(min(vals), 4), round(max(vals), 4), len(vals), scope,
                      [{"name": o.name, "doc_ref": o.doc_ref, "capacity": o.capacity, "per_m2": round(v, 4)}
                       for o, v in found])


def fmt(x: float, digits: int = 2) -> str:
    s = f"{x:,.{digits}f}".replace(",", " ").replace(".", ",")
    return s
