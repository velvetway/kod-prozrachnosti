"""HTTP API и раздача собранного интерфейса."""
import json
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import report
from .config import (DEMO_DIR, DEFAULT_ESCALATION_THRESHOLDS, DEFAULT_PRICE_THRESHOLDS, DEFAULT_VOLUME_THRESHOLDS,
                     FRONTEND_DIST, MAX_UPLOAD_BYTES)
from .core import matching, pipeline
from .core.calc import q_key
from .core.parser import ParseError
from .db import get_session
from .models import (AnalogObject, Check, CheckItem, DatasetVersion, Decision, PriceIndex, PriceZone,
                     ReferencePrice, Region, Resource, Signal)
from .reference import loader


@asynccontextmanager
async def lifespan(_: FastAPI):
    loader.init_db()
    yield


app = FastAPI(title="Мониторинг ценовых рисков в закупках строительных материалов", version="0.1.0",
              lifespan=lifespan)

DECISIONS = ["Отклонение обосновано", "Запросить обоснование цены", "Передать на проверку",
             "Сопоставление неверно"]
OBJECT_TYPES = ["Школа", "Поликлиника", "Дорога, благоустройство"]


# ---------------------------------------------------------------- сериализация
def _zone(z: PriceZone | None):
    return {"id": z.id, "number": z.number, "name": z.name} if z else None


def _signal(sg: Signal, full: bool = False) -> dict:
    d = {"id": sg.id, "kind": sg.kind, "level": sg.level, "actual": sg.actual, "benchmark": sg.benchmark,
         "deviation_pct": sg.deviation_pct, "overpay": sg.overpay, "formula": sg.formula,
         "decision": ({"outcome": sg.decisions[-1].outcome, "at": sg.decisions[-1].created_at.isoformat()}
                      if sg.decisions else None)}
    if full:
        d["details"] = sg.details
        d["decisions"] = [{"id": x.id, "outcome": x.outcome, "comment": x.comment, "author": x.author,
                           "at": x.created_at.isoformat()} for x in sg.decisions]
    else:
        d["note"] = (sg.details or {}).get("note", "")
        if sg.kind == "volume":
            d["corridor"] = [sg.details.get("low"), sg.details.get("high")]
    return d


def _item(it: CheckItem) -> dict:
    m = it.match
    return {
        "id": it.id, "position": it.position, "row": it.source_row, "code": it.code, "name": it.name,
        "unit": it.unit, "quantity": it.quantity, "price": it.price, "base_price": it.base_price,
        "match": {"resource": ({"id": m.resource.id, "code": m.resource.code, "name": m.resource.name,
                                "unit": m.resource.unit, "group": m.resource.group} if m.resource else None),
                  "method": m.method, "score": m.score, "level": m.level, "unit_factor": m.unit_factor,
                  "note": m.note} if m else None,
        "signals": [_signal(sg) for sg in it.signals],
    }


def _check_brief(c: Check) -> dict:
    return {"id": c.id, "number": c.number, "title": c.title, "file_name": c.file_name,
            "region": c.region.name, "zone": _zone(c.zone), "quarter": c.quarter, "status": c.status,
            "object_type": c.object_type, "capacity": c.capacity, "created_at": c.created_at.isoformat(),
            "summary": pipeline.summary(c),
            "is_demo": any(v.get("is_demo") for v in c.data_versions.values())}


def _get_check(s: Session, check_id: int) -> Check:
    c = s.get(Check, check_id)
    if not c:
        raise HTTPException(404, "Проверка не найдена")
    return c


# ---------------------------------------------------------------- справочники
@app.get("/api/meta")
def meta(s: Session = Depends(get_session)):
    quarters = sorted({q for (q,) in s.execute(select(ReferencePrice.quarter).distinct())} |
                      {q for (q,) in s.execute(select(PriceIndex.quarter).distinct())}, key=q_key)
    versions = [{"code": d.code, "kind": d.kind, "records": d.records, "sha256": d.sha256, "is_demo": d.is_demo,
                 "source_file": d.source_file, "loaded_at": d.loaded_at.isoformat(), "note": d.note}
                for d in s.scalars(select(DatasetVersion).order_by(DatasetVersion.id.desc()))]
    return {"quarters": quarters, "object_types": OBJECT_TYPES, "decisions": DECISIONS,
            "defaults": {"price_thresholds": DEFAULT_PRICE_THRESHOLDS, "volume_thresholds": DEFAULT_VOLUME_THRESHOLDS,
                         "escalation_thresholds": DEFAULT_ESCALATION_THRESHOLDS},
            "datasets": versions, "is_demo": any(v["is_demo"] for v in versions)}


@app.get("/api/regions")
def regions(s: Session = Depends(get_session)):
    with_prices = {rid for (rid,) in s.execute(select(ReferencePrice.region_id).distinct())}
    out = []
    for r in s.scalars(select(Region).order_by(Region.federal_district, Region.name)):
        out.append({"id": r.id, "name": r.name, "federal_district": r.federal_district, "is_pilot": r.is_pilot,
                    "has_prices": r.id in with_prices, "zones": [_zone(z) for z in r.zones]})
    out.sort(key=lambda x: (not x["is_pilot"], not x["has_prices"], x["name"]))
    return out


@app.get("/api/reference/prices")
def reference_prices(region_id: int, quarter: str, zone_id: int | None = None, s: Session = Depends(get_session)):
    from .core import calc
    region = s.get(Region, region_id)
    if not region:
        raise HTTPException(404, "Регион не найден")
    idx = calc.IndexBook(s, region_id)
    out = []
    for res in s.scalars(select(Resource).order_by(Resource.code)):
        bm = calc.benchmark(s, res, region_id, zone_id, quarter, ["fgiscs", "eis", "market"], idx)
        if not bm.sources:
            continue
        out.append({"code": res.code, "name": res.name, "unit": res.unit, "group": res.group,
                    "benchmark": bm.value,
                    "sources": {sv.source: {"value": sv.value, "count": len(sv.rows)} for sv in bm.sources}})
    return out


@app.get("/api/reference/analogs")
def analogs(region_id: int, s: Session = Depends(get_session)):
    res = {r.code: r for r in s.scalars(select(Resource))}
    return [{"id": a.id, "object_type": a.object_type, "name": a.name, "capacity": a.capacity, "doc_ref": a.doc_ref,
             "consumption": [{"code": k, "name": res[k].name if k in res else k,
                              "unit": res[k].unit if k in res else "", "per_m2": v}
                             for k, v in sorted(a.consumption.items())]}
            for a in s.scalars(select(AnalogObject).where(AnalogObject.region_id == region_id)
                               .order_by(AnalogObject.object_type, AnalogObject.id))]


@app.get("/api/resources")
def resources(q: str = "", unit: str = "", s: Session = Depends(get_session)):
    rows = list(s.scalars(select(Resource).order_by(Resource.code)))
    if unit or q:
        cands = matching.candidates("", q, unit, rows, limit=10) if unit else []
        if cands:
            return [{"id": c.resource_id, "code": c.code, "name": c.name, "unit": c.unit, "score": c.score}
                    for c in cands]
    return [{"id": r.id, "code": r.code, "name": r.name, "unit": r.unit, "score": None} for r in rows]


@app.post("/api/reference/import")
async def import_reference(kind: str = Form(...), file: UploadFile = File(...), note: str = Form(""),
                           s: Session = Depends(get_session)):
    data = await file.read()
    fns = {"prices": loader.import_prices, "indexes": loader.import_indexes, "analogs": loader.import_analogs}
    try:
        if kind == "resources":
            n = loader.import_resources(s, data)
            s.commit()
            return {"ok": True, "records": n}
        if kind not in fns:
            raise HTTPException(400, "Вид справочника: prices, indexes, analogs или resources")
        dv = fns[kind](s, data, file.filename or "upload.csv", False, note)
        s.commit()
        return {"ok": True, "version": dv.code, "records": dv.records}
    except loader.ImportError_ as e:
        s.rollback()
        raise HTTPException(422, str(e))


# ---------------------------------------------------------------- проверки
@app.get("/api/checks")
def list_checks(region_id: int | None = None, level: list[str] = Query(default=[]), status: list[str] = Query(default=[]),
                q: str = "", s: Session = Depends(get_session)):
    stmt = select(Check).order_by(Check.id.desc())
    if region_id:
        stmt = stmt.where(Check.region_id == region_id)
    out = []
    for c in s.scalars(stmt):
        b = _check_brief(c)
        if level and b["summary"]["max_level"] not in level:
            continue
        if status and c.status not in status:
            continue
        if q:
            hay = " ".join([c.number, c.title, c.file_name] + [it.name for it in c.items] +
                           [it.match.resource.code for it in c.items if it.match and it.match.resource]).lower()
            if q.lower() not in hay:
                continue
        out.append(b)
    return out


def _thr(raw: str | None, default):
    if not raw:
        return default
    try:
        a, b = [float(x) for x in json.loads(raw)]
    except Exception:
        raise HTTPException(422, "Пороги заданы неверно")
    if not 0 < a < b:
        raise HTTPException(422, "Порог среднего сигнала должен быть больше нуля и меньше порога высокого")
    return a, b


@app.post("/api/checks")
async def create_check(file: UploadFile = File(...), region_id: int = Form(...), zone_id: int | None = Form(None),
                       quarter: str = Form(...), object_type: str = Form(""), capacity: float | None = Form(None),
                       base_quarter: str = Form(""), sources: str = Form('["fgiscs","eis","market"]'),
                       price_thresholds: str = Form(""), volume_thresholds: str = Form(""),
                       escalation_thresholds: str = Form(""), title: str = Form(""),
                       s: Session = Depends(get_session)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Файл больше 20 МБ")
    region = s.get(Region, region_id)
    if not region:
        raise HTTPException(422, "Регион не найден")
    if zone_id and not any(z.id == zone_id for z in region.zones):
        raise HTTPException(422, "Ценовая зона не относится к выбранному региону")
    if object_type and object_type not in OBJECT_TYPES:
        raise HTTPException(422, "Неизвестный тип объекта")
    try:
        check, warnings = pipeline.create_check(
            s, data, file.filename or "document.xlsx", region_id=region_id, zone_id=zone_id or None,
            quarter=quarter, object_type=object_type or None, capacity=capacity or None,
            base_quarter=base_quarter or None, sources=json.loads(sources),
            price_thresholds=_thr(price_thresholds, None), volume_thresholds=_thr(volume_thresholds, None),
            escalation_thresholds=_thr(escalation_thresholds, None), title=title or None)
    except ParseError as e:
        s.rollback()
        raise HTTPException(422, str(e))
    s.commit()
    return {"id": check.id, "number": check.number, "warnings": warnings}


@app.get("/api/checks/{check_id}")
def get_check(check_id: int, s: Session = Depends(get_session)):
    c = _get_check(s, check_id)
    b = _check_brief(c)
    b.update({"file_sha256": c.file_sha256, "base_quarter": c.base_quarter, "params": c.params,
              "data_versions": c.data_versions, "result_sha256": c.result_sha256,
              "items": [_item(it) for it in c.items]})
    return b


@app.post("/api/checks/{check_id}/rerun")
def rerun(check_id: int, s: Session = Depends(get_session)):
    """Повторный расчёт на тех же данных: сравнивает контрольную сумму результата."""
    c = _get_check(s, check_id)
    before = c.result_sha256
    decisions = {(sg.item_id, sg.kind): [(d.outcome, d.comment, d.author, d.created_at) for d in sg.decisions]
                 for it in c.items for sg in it.signals}
    pipeline.run(s, c)
    for it in c.items:
        for sg in it.signals:
            for outcome, comment, author, at in decisions.get((sg.item_id, sg.kind), []):
                s.add(Decision(signal_id=sg.id, outcome=outcome, comment=comment, author=author, created_at=at))
    s.flush()
    for it in c.items:
        for sg in it.signals:
            s.refresh(sg)
    pipeline.refresh_status(c)
    s.commit()
    return {"before": before, "after": c.result_sha256, "identical": before == c.result_sha256}


@app.delete("/api/checks/{check_id}")
def delete_check(check_id: int, s: Session = Depends(get_session)):
    s.delete(_get_check(s, check_id))
    s.commit()
    return {"ok": True}


@app.get("/api/checks/{check_id}/report.docx")
def check_report(check_id: int, s: Session = Depends(get_session)):
    c = _get_check(s, check_id)
    data = report.build(c)
    name = f"Отчёт_{c.number}.docx"
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@app.get("/api/items/{item_id}/candidates")
def item_candidates(item_id: int, s: Session = Depends(get_session)):
    it = s.get(CheckItem, item_id)
    if not it:
        raise HTTPException(404, "Позиция не найдена")
    rows = list(s.scalars(select(Resource).order_by(Resource.code)))
    return [{"id": c.resource_id, "code": c.code, "name": c.name, "unit": c.unit, "score": c.score,
             "level": matching.level(c.score)} for c in matching.candidates(it.code, it.name, it.unit, rows, 8)]


class ManualMatch(BaseModel):
    resource_id: int


@app.post("/api/items/{item_id}/match")
def item_match(item_id: int, body: ManualMatch, s: Session = Depends(get_session)):
    it = s.get(CheckItem, item_id)
    res = s.get(Resource, body.resource_id)
    if not it or not res:
        raise HTTPException(404, "Позиция или ресурс не найдены")
    try:
        pipeline.set_manual_match(s, it, res)
    except ValueError as e:
        raise HTTPException(422, str(e))
    s.commit()
    return _item(it)


# ---------------------------------------------------------------- сигналы и решения
@app.get("/api/signals/{signal_id}")
def get_signal(signal_id: int, s: Session = Depends(get_session)):
    sg = s.get(Signal, signal_id)
    if not sg:
        raise HTTPException(404, "Сигнал не найден")
    it = sg.item
    c = it.check
    return {"signal": _signal(sg, full=True), "item": _item(it),
            "check": {"id": c.id, "number": c.number, "title": c.title, "region": c.region.name,
                      "zone": _zone(c.zone), "quarter": c.quarter, "object_type": c.object_type,
                      "capacity": c.capacity, "data_versions": c.data_versions, "params": c.params,
                      "result_sha256": c.result_sha256}}


class DecisionIn(BaseModel):
    outcome: str
    comment: str = Field("", max_length=2000)


@app.post("/api/signals/{signal_id}/decision")
def add_decision(signal_id: int, body: DecisionIn, s: Session = Depends(get_session)):
    sg = s.get(Signal, signal_id)
    if not sg:
        raise HTTPException(404, "Сигнал не найден")
    if body.outcome not in DECISIONS:
        raise HTTPException(422, "Неизвестный вариант решения")
    s.add(Decision(signal_id=sg.id, outcome=body.outcome, comment=body.comment.strip()))
    s.flush()
    s.refresh(sg)
    pipeline.refresh_status(sg.item.check)
    s.commit()
    return _signal(sg, full=True)


@app.get("/api/journal")
def journal(s: Session = Depends(get_session)):
    out = []
    for d in s.scalars(select(Decision).order_by(Decision.id.desc())):
        sg, it = d.signal, d.signal.item
        out.append({"id": d.id, "at": d.created_at.isoformat(), "author": d.author, "outcome": d.outcome,
                    "comment": d.comment, "signal_id": sg.id, "kind": sg.kind, "level": sg.level,
                    "deviation_pct": sg.deviation_pct, "item": it.name, "check_id": it.check.id,
                    "check_number": it.check.number, "region": it.check.region.name})
    return out


@app.get("/api/demo")
def demo_files(s: Session = Depends(get_session)):
    """Демонстрационные сметы с заранее известными отклонениями и параметрами для подстановки в форму."""
    manifest = DEMO_DIR / "expected.json"
    if not manifest.exists():
        return []
    out = []
    for d in json.loads(manifest.read_text(encoding="utf-8")):
        region = s.scalar(select(Region).where(Region.name == d["region"]))
        zone = next((z for z in region.zones if z.number == d["zone"]), None) if region else None
        out.append({"file": d["file"], "title": d["title"], "region_id": region.id if region else None,
                    "zone_id": zone.id if zone else None, "quarter": d["quarter"], "object_type": d["object_type"],
                    "capacity": d["capacity"], "base_quarter": d["base_quarter"],
                    "expected": d["items"]})
    return out


@app.get("/api/demo/{name}")
def demo_file(name: str):
    path = (DEMO_DIR / name).resolve()
    if path.parent != DEMO_DIR.resolve() or not path.is_file() or path.suffix != ".xlsx":
        raise HTTPException(404, "Файл не найден")
    return FileResponse(path, filename=name)


@app.get("/api/health")
def health(s: Session = Depends(get_session)):
    return {"ok": True, "checks": s.scalar(select(func.count()).select_from(Check))}


# ---------------------------------------------------------------- интерфейс
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        target = FRONTEND_DIST / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
