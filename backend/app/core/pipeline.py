"""Конвейер проверки: документ → позиции → сопоставление → ориентиры → отклонения → сигналы."""
import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import (DEFAULT_ESCALATION_THRESHOLDS, DEFAULT_PRICE_THRESHOLDS,
                      DEFAULT_VOLUME_THRESHOLDS)
from ..models import Check, CheckItem, DatasetVersion, Match, ReferencePrice, Resource, Signal
from . import calc, matching, parser
from .calc import fmt

ACTIVE_LEVELS = ("high", "medium", "review")


def _current_versions(s: Session) -> dict:
    """Все загруженные версии справочников (каждая проверка ссылается на них)."""
    out: dict[str, dict] = {}
    for dv in s.scalars(select(DatasetVersion).order_by(DatasetVersion.id)):
        out[dv.code] = {"kind": dv.kind, "sha256": dv.sha256, "is_demo": dv.is_demo, "records": dv.records,
                        "source_file": dv.source_file}
    return out


def _next_number(s: Session) -> str:
    n = s.scalar(select(func.count()).select_from(Check)) or 0
    return f"ПР-2026-{n + 1:04d}"


def create_check(s: Session, data: bytes, file_name: str, *, region_id: int, zone_id: int | None,
                 quarter: str, object_type: str | None, capacity: float | None, base_quarter: str | None,
                 sources: list[str], price_thresholds=None, volume_thresholds=None,
                 escalation_thresholds=None, title: str | None = None) -> tuple[Check, list[str]]:
    doc = parser.parse(data, file_name)
    params = {
        "sources": [x for x in ("fgiscs", "eis", "market") if x in sources],
        "price_thresholds": list(price_thresholds or DEFAULT_PRICE_THRESHOLDS),
        "volume_thresholds": list(volume_thresholds or DEFAULT_VOLUME_THRESHOLDS),
        "escalation_thresholds": list(escalation_thresholds or DEFAULT_ESCALATION_THRESHOLDS),
    }
    if not params["sources"]:
        raise parser.ParseError("Выберите хотя бы один источник ценовых ориентиров")
    check = Check(number=_next_number(s), title=title or doc.title, file_name=file_name,
                  file_sha256=hashlib.sha256(data).hexdigest(), region_id=region_id, zone_id=zone_id,
                  quarter=quarter, base_quarter=base_quarter if doc.has_base_price else None,
                  object_type=object_type or None, capacity=capacity or None, params=params,
                  data_versions=_current_versions(s))
    s.add(check)
    s.flush()
    for pos, it in enumerate(doc.items, start=1):
        s.add(CheckItem(check_id=check.id, position=pos, source_row=it.row, code=it.code, name=it.name,
                        unit=it.unit, quantity=it.quantity, price=it.price, base_price=it.base_price))
    s.flush()
    s.refresh(check)
    warnings = list(doc.warnings)
    if doc.has_base_price and not base_quarter:
        warnings.append("В документе есть исходные цены, но не указан квартал исходной цены — "
                        "проверка удорожания не выполнена")
    run(s, check)
    return check, warnings


def _match_item(item: CheckItem, resources: list[Resource]) -> Match:
    cand = matching.best(item.code, item.name, item.unit, resources)
    if not cand:
        top = matching.candidates(item.code, item.name, item.unit, resources, limit=1)
        note = (f"Лучший кандидат «{top[0].name}» ({top[0].score:.2f}) ниже порога сопоставимости"
                if top else "Нет ресурсов с совместимой единицей измерения")
        return Match(item_id=item.id, resource_id=None, method="none", score=top[0].score if top else 0.0,
                     level="Нет", unit_factor=1.0, note=note)
    note = "Совпал код КСР" if cand.method == "code" else "Сопоставлено по наименованию и характеристикам"
    if cand.unit_factor != 1.0:
        note += f"; единица «{item.unit}» пересчитана в «{cand.unit}» (×{cand.unit_factor:g})"
    return Match(item_id=item.id, resource_id=cand.resource_id, method=cand.method, score=cand.score,
                 level=matching.level(cand.score), unit_factor=cand.unit_factor, note=note)


def evaluate_item(s: Session, check: Check, item: CheckItem, idx: calc.IndexBook) -> None:
    """Пересчитывает сигналы позиции по текущему сопоставлению."""
    for sig in list(item.signals):
        s.delete(sig)
    s.flush()
    m = item.match
    p = check.params
    if not m or not m.resource_id:
        s.add(Signal(item_id=item.id, kind="price", level="nomatch", formula="",
                     details={"note": m.note if m else "Не сопоставлено"}))
        return
    res = s.get(Resource, m.resource_id)
    f = m.unit_factor
    qty_res = item.quantity * f
    price_res = item.price / f

    # --- цена
    bm = calc.benchmark(s, res, check.region_id, check.zone_id, check.quarter, p["sources"], idx)
    if bm.value:
        dev = (price_res - bm.value) / bm.value * 100
        level = calc.classify(dev, tuple(p["price_thresholds"]))
        if m.level == "Низкая" and level != "none":
            level = "review"
        overpay = max(0.0, price_res - bm.value) * qty_res
        formula = f"({fmt(price_res)} − {fmt(bm.value)}) / {fmt(bm.value)} × 100 % = {fmt(dev, 1)} %"
        details = {
            "unit": res.unit, "quantity_res": round(qty_res, 4),
            "sources": [{"source": sv.source, "title": calc.SOURCE_TITLES[sv.source], "value": sv.value,
                         "count": len(sv.rows), "rows": sv.rows, "note": sv.note, "synthetic": sv.synthetic}
                        for sv in bm.sources],
            "method": "медиана значений источников" if len(bm.sources) > 1 else "единственный источник",
            "thresholds": p["price_thresholds"], "notes": bm.notes,
            "overpay_formula": f"({fmt(price_res)} − {fmt(bm.value)}) × {fmt(qty_res, 3)} {res.unit} = {fmt(overpay)} ₽"
            if overpay > 0 else "Превышения нет",
        }
        s.add(Signal(item_id=item.id, kind="price", level=level, actual=round(price_res, 2),
                     benchmark=bm.value, deviation_pct=round(dev, 2), overpay=round(overpay, 2),
                     formula=formula, details=details))
    else:
        s.add(Signal(item_id=item.id, kind="price", level="nodata", formula="",
                     details={"note": "; ".join(bm.notes) or "Нет ценовых ориентиров"}))
    fair_price = bm.value or price_res

    # --- объём на единицу мощности
    if check.object_type and check.capacity:
        norm = calc.volume_norm(s, res.code, check.region_id, check.object_type)
        if norm:
            fact = qty_res / check.capacity
            dev = (fact - norm.median) / norm.median * 100
            level = calc.classify(dev, tuple(p["volume_thresholds"]))
            excess = max(0.0, qty_res - norm.median * check.capacity)
            overpay = excess * fair_price
            s.add(Signal(
                item_id=item.id, kind="volume", level=level, actual=round(fact, 4), benchmark=norm.median,
                deviation_pct=round(dev, 2), overpay=round(overpay, 2),
                formula=(f"{fmt(qty_res, 3)} {res.unit} / {fmt(check.capacity, 0)} м² = {fmt(fact, 4)} "
                         f"{res.unit}/м²; ({fmt(fact, 4)} − {fmt(norm.median, 4)}) / {fmt(norm.median, 4)} × 100 % "
                         f"= {fmt(dev, 1)} %"),
                details={"unit": res.unit, "median": norm.median, "low": norm.low, "high": norm.high,
                         "count": norm.count, "scope": norm.scope, "analogs": norm.analogs,
                         "excess_qty": round(excess, 4), "thresholds": p["volume_thresholds"],
                         "overpay_formula": (f"({fmt(qty_res, 3)} − {fmt(norm.median, 4)} × {fmt(check.capacity, 0)}) "
                                             f"× {fmt(fair_price)} = {fmt(overpay)} ₽") if overpay > 0 else
                         "Перерасхода нет"}))

    # --- удорожание относительно индекса
    if check.base_quarter and item.base_price:
        k, info = idx.coef(res, check.base_quarter, check.quarter)
        if info["ok"]:
            claimed = (item.price / item.base_price - 1) * 100
            allowed = (k - 1) * 100
            excess = ((item.price / item.base_price) / k - 1) * 100
            level = calc.classify(excess, tuple(p["escalation_thresholds"]))
            overpay = max(0.0, item.price - item.base_price * k) * item.quantity
            s.add(Signal(
                item_id=item.id, kind="escalation", level=level, actual=round(claimed, 2),
                benchmark=round(allowed, 2), deviation_pct=round(excess, 2), overpay=round(overpay, 2),
                formula=(f"Заявлено: {fmt(item.price)} / {fmt(item.base_price)} = {fmt(claimed, 1)} %; "
                         f"индекс {check.base_quarter} → {check.quarter}: {fmt(allowed, 1)} %; "
                         f"превышение: {fmt(item.price / item.base_price, 4)} / {fmt(k, 4)} − 1 = {fmt(excess, 1)} %"),
                details={"base_price": item.base_price, "base_quarter": check.base_quarter, "index": round(k, 4),
                         "group": res.group, "index_basis": info["title"], "index_n": info["n"],
                         "thresholds": p["escalation_thresholds"],
                         "overpay_formula": (f"({fmt(item.price)} − {fmt(item.base_price)} × {fmt(k, 4)}) × "
                                             f"{fmt(item.quantity, 3)} {item.unit} = {fmt(overpay)} ₽")
                         if overpay > 0 else "Превышения нет"}))


def result_digest(check: Check) -> str:
    payload = {
        "file": check.file_sha256, "region": check.region_id, "zone": check.zone_id, "quarter": check.quarter,
        "base_quarter": check.base_quarter, "object": [check.object_type, check.capacity],
        "params": check.params, "data": check.data_versions,
        "items": [{
            "pos": it.position,
            "match": [it.match.resource_id, round(it.match.score, 4)] if it.match else None,
            "signals": sorted([[sg.kind, sg.level, sg.benchmark, sg.deviation_pct, sg.overpay] for sg in it.signals],
                              key=lambda x: x[0]),
        } for it in check.items],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def refresh_status(check: Check) -> None:
    active = [sg for it in check.items for sg in it.signals if sg.level in ACTIVE_LEVELS]
    if not active:
        check.status = "Без сигналов"
    elif all(sg.decisions for sg in active):
        check.status = "Решение принято"
    else:
        check.status = "Ожидает решения"


def region_resources(s: Session, region_id: int) -> list[Resource]:
    """Ресурсы, для которых в регионе есть хотя бы одна цена; если таких нет — весь классификатор."""
    priced = select(ReferencePrice.resource_id).where(ReferencePrice.region_id == region_id).distinct()
    found = list(s.scalars(select(Resource).where(Resource.id.in_(priced)).order_by(Resource.code)))
    return found or list(s.scalars(select(Resource).order_by(Resource.code)))


def run(s: Session, check: Check, rematch: bool = True) -> None:
    resources = region_resources(s, check.region_id)
    known = {r.code for r in resources}
    codes = {it.code for it in check.items if it.code and it.code not in known}
    if codes:   # ресурс с указанным кодом сопоставляется, даже если в регионе для него нет цены
        resources += list(s.scalars(select(Resource).where(Resource.code.in_(codes))))
    idx = calc.IndexBook(s, check.region_id)
    for item in check.items:
        if rematch or not item.match:
            if item.match and item.match.method == "manual":
                pass
            else:
                if item.match:
                    s.delete(item.match)
                    s.flush()
                item.match = _match_item(item, resources)
                s.add(item.match)
        s.flush()
        evaluate_item(s, check, item, idx)
    s.flush()
    for item in check.items:
        s.refresh(item)
    check.result_sha256 = result_digest(check)
    refresh_status(check)
    s.flush()


def set_manual_match(s: Session, item: CheckItem, resource: Resource) -> None:
    from . import units
    f = units.factor(item.unit, resource.unit)
    if f is None:
        raise ValueError(f"Единица «{item.unit}» несовместима с единицей ресурса «{resource.unit}»")
    if item.match:
        s.delete(item.match)
        s.flush()
    item.match = Match(item_id=item.id, resource_id=resource.id, method="manual", score=1.0, level="Ручное",
                       unit_factor=f, note="Сопоставлено специалистом вручную")
    s.add(item.match)
    s.flush()
    check = item.check
    evaluate_item(s, check, item, calc.IndexBook(s, check.region_id))
    s.flush()
    for it in check.items:
        s.refresh(it)
    check.result_sha256 = result_digest(check)
    refresh_status(check)
    s.flush()


def summary(check: Check) -> dict:
    sigs = [sg for it in check.items for sg in it.signals]
    active = [sg for sg in sigs if sg.level in ACTIVE_LEVELS]
    by = lambda kind: round(sum(sg.overpay for sg in sigs if sg.kind == kind and sg.level in ("high", "medium")), 2)
    return {
        "items": len(check.items),
        "matched": sum(1 for it in check.items if it.match and it.match.resource_id),
        "high": sum(1 for sg in active if sg.level == "high"),
        "medium": sum(1 for sg in active if sg.level == "medium"),
        "review": sum(1 for sg in active if sg.level == "review"),
        "overpay_price": by("price"), "overpay_volume": by("volume"), "overpay_escalation": by("escalation"),
        "max_level": "high" if any(sg.level == "high" for sg in active) else
                     "medium" if any(sg.level == "medium" for sg in active) else
                     "review" if active else "none",
        "decided": sum(1 for sg in active if sg.decisions),
        "total_contract": round(sum(it.quantity * it.price for it in check.items), 2),
    }
