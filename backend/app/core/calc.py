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
    synthetic: bool = False


@dataclass
class Benchmark:
    value: float | None
    sources: list[SourceValue]
    notes: list[str]


def group_levels(code: str) -> list[tuple[str, str]]:
    """Уровни группировки ресурса для индекса: раздел КСР, книга КСР, все материалы."""
    head = code.split("-")[0].split(".")
    out = []
    if len(head) >= 3:
        out.append(("section", ".".join(head[:3])))
    if head and head[0]:
        out.append(("book", head[0]))
    out.append(("all", ""))
    return out


LEVEL_TITLES = {"section": "раздел КСР {key}", "book": "книга КСР {key}", "all": "все материалы региона",
                "table": "индекс из справочника, группа «{key}»", "same": "тот же квартал"}


class IndexBook:
    """Индексы изменения цен между кварталами для региона.

    Если в справочник загружен индекс для группы ресурса — берётся он. Иначе индекс считается
    из сметных цен ФГИС ЦС этого региона: медиана отношений цен одних и тех же ресурсов
    группы в двух кварталах. Группа — раздел КСР; если в разделе меньше трёх общих ресурсов,
    берётся книга КСР, затем все материалы региона."""

    MIN_COMMON = 3

    def __init__(self, s: Session, region_id: int):
        self.table: dict[tuple[str, str], float] = {
            (p.group, p.quarter): p.value
            for p in s.scalars(select(PriceIndex).where(PriceIndex.region_id == region_id))
        }
        self.prices: dict[str, dict[str, float]] = {}
        rows = s.execute(select(ReferencePrice.quarter, Resource.code, ReferencePrice.price)
                         .join(Resource, Resource.id == ReferencePrice.resource_id)
                         .where(ReferencePrice.region_id == region_id, ReferencePrice.source == "fgiscs")
                         .order_by(ReferencePrice.id))
        for q, code, price in rows:
            if price > 0:
                self.prices.setdefault(q, {})[code] = price
        self._cache: dict[tuple, tuple[float, dict]] = {}

    def coef(self, resource: Resource, from_q: str, to_q: str) -> tuple[float, dict]:
        """Коэффициент пересчёта цены из квартала from_q в to_q и сведения о его происхождении."""
        if from_q == to_q:
            return 1.0, {"level": "same", "title": LEVEL_TITLES["same"], "n": 0, "ok": True}
        a, b = self.table.get((resource.group, from_q)), self.table.get((resource.group, to_q))
        if a and b:
            return b / a, {"level": "table", "title": LEVEL_TITLES["table"].format(key=resource.group), "n": 0, "ok": True}
        key = (resource.code, from_q, to_q)
        if key in self._cache:
            return self._cache[key]
        p_from, p_to = self.prices.get(from_q, {}), self.prices.get(to_q, {})
        common = [c for c in p_to if c in p_from]
        result = (1.0, {"level": "none", "title": "нет данных для индекса", "n": 0, "ok": False})
        for level, prefix in group_levels(resource.code):
            if level == "section":
                ratios = [p_to[c] / p_from[c] for c in common if c.split("-")[0].startswith(prefix + ".") or c.split("-")[0] == prefix]
            elif level == "book":
                ratios = [p_to[c] / p_from[c] for c in common if c.split(".")[0] == prefix]
            else:
                ratios = [p_to[c] / p_from[c] for c in common]
            if len(ratios) >= self.MIN_COMMON:
                result = (median(ratios), {"level": level, "title": LEVEL_TITLES[level].format(key=prefix),
                                           "n": len(ratios), "ok": True})
                break
        self._cache[key] = result
        return result


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
            earlier = [r for r in src_rows if q_key(r.quarter) < q_key(quarter)]
            later = [r for r in src_rows if q_key(r.quarter) > q_key(quarter)]
            chosen = [exact[0] if exact else earlier[-1] if earlier else later[0]]
            if not exact:
                notes.append(f"Сметной цены ФГИС ЦС за {quarter} нет — взята цена за {chosen[0].quarter} с пересчётом индексом")
        else:
            chosen = src_rows
        detail, values, missing_index = [], [], False
        synthetic = any(r.dataset.is_demo for r in chosen)
        for r in chosen:
            k, info = idx.coef(resource, r.quarter, quarter)
            missing_index |= not info["ok"]
            v = r.price * k
            values.append(v)
            detail.append({"doc_ref": r.doc_ref, "doc_url": r.doc_url, "quarter": r.quarter,
                           "price": round(r.price, 2), "index": round(k, 4), "indexed": round(v, 2),
                           "index_basis": info["title"] + (f", ресурсов: {info['n']}" if info["n"] else ""),
                           "synthetic": r.dataset.is_demo})
        note = "нет данных для индекса — цена взята без пересчёта" if missing_index else ""
        out.append(SourceValue(src, round(median(values), 2), detail, note, synthetic))
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
