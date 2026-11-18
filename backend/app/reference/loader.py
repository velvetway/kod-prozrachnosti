"""Загрузка справочников из CSV. Каждый загруженный файл — отдельная версия набора данных
(код, контрольная сумма, число записей), которая записывается в каждую проверку."""
import csv
import hashlib
import io
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import REFERENCE_DIR
from ..db import Base, engine
from ..models import (AnalogObject, DatasetVersion, PriceIndex, PriceZone, ReferencePrice, Region,
                      Resource)
from .regions import PILOT_REGIONS, REGIONS

PRICE_SOURCES = {"fgiscs", "eis", "market"}


class ImportError_(ValueError):
    """Ошибка формата загружаемого файла (сообщение показывается пользователю)."""


def _rows(data: bytes) -> list[dict]:
    text = data.decode("utf-8-sig")
    sample = text[:2000]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items()}
            for row in csv.DictReader(io.StringIO(text), delimiter=delimiter)]


def _need(row: dict, cols: list[str], line: int) -> None:
    missing = [c for c in cols if not row.get(c)]
    if missing:
        raise ImportError_(f"Строка {line}: не заполнены поля {', '.join(missing)}")


def _num(value: str, line: int, field: str) -> float:
    try:
        return float(value.replace(" ", "").replace(" ", "").replace(",", "."))
    except ValueError:
        raise ImportError_(f"Строка {line}: поле {field} должно быть числом, получено «{value}»")


def _new_version(s: Session, kind: str, file_name: str, data: bytes, records: int, is_demo: bool,
                 note: str) -> DatasetVersion:
    sha = hashlib.sha256(data).hexdigest()
    n = s.scalar(select(func.count()).select_from(DatasetVersion).where(DatasetVersion.kind == kind)) or 0
    dv = DatasetVersion(code=f"{kind}-v{n + 1}{'-demo' if is_demo else ''}", kind=kind,
                        source_file=file_name, sha256=sha, records=records, is_demo=is_demo, note=note)
    s.add(dv)
    s.flush()
    return dv


def _region(s: Session, name: str, line: int) -> Region:
    r = s.scalar(select(Region).where(Region.name == name))
    if not r:
        raise ImportError_(f"Строка {line}: регион «{name}» не найден в справочнике субъектов РФ")
    return r


def _zone(s: Session, region: Region, number: str, line: int, name: str | None = None) -> PriceZone | None:
    if not number:
        return None
    num = int(_num(number, line, "zone"))
    z = s.scalar(select(PriceZone).where(PriceZone.region_id == region.id, PriceZone.number == num))
    if not z:
        z = PriceZone(region_id=region.id, number=num, name=name or f"Ценовая зона {num}")
        s.add(z)
        s.flush()
    elif name and z.name != name:
        z.name = name
    return z


def seed_regions(s: Session) -> None:
    if s.scalar(select(func.count()).select_from(Region)):
        return
    for district, names in REGIONS.items():
        for name in names:
            s.add(Region(name=name, federal_district=district, is_pilot=name in PILOT_REGIONS))
    s.flush()


def import_resources(s: Session, data: bytes) -> int:
    rows = _rows(data)
    for i, row in enumerate(rows, start=2):
        _need(row, ["ksr_code", "name", "unit"], i)
        res = s.scalar(select(Resource).where(Resource.code == row["ksr_code"]))
        if not res:
            res = Resource(code=row["ksr_code"])
            s.add(res)
        res.name, res.unit = row["name"], row["unit"]
        res.group = row.get("group") or "Прочее"
        res.attributes = row.get("attributes", "")
    s.flush()
    return len(rows)


def import_zones(s: Session, data: bytes) -> int:
    rows = _rows(data)
    for i, row in enumerate(rows, start=2):
        _need(row, ["region", "zone", "name"], i)
        _zone(s, _region(s, row["region"], i), row["zone"], i, row["name"])
    s.flush()
    return len(rows)


def import_prices(s: Session, data: bytes, file_name: str, is_demo: bool = False, note: str = "") -> DatasetVersion:
    rows = _rows(data)
    if not rows:
        raise ImportError_("Файл не содержит строк с ценами")
    dv = _new_version(s, "prices", file_name, data, len(rows), is_demo, note)
    resources = {r.code: r for r in s.scalars(select(Resource))}
    for i, row in enumerate(rows, start=2):
        _need(row, ["source", "ksr_code", "region", "quarter", "price"], i)
        if row["source"] not in PRICE_SOURCES:
            raise ImportError_(f"Строка {i}: источник должен быть одним из {', '.join(sorted(PRICE_SOURCES))}")
        res = resources.get(row["ksr_code"])
        if not res:
            if not (row.get("name") and row.get("unit")):
                raise ImportError_(f"Строка {i}: ресурс {row['ksr_code']} не найден; добавьте колонки name и unit")
            res = Resource(code=row["ksr_code"], name=row["name"], unit=row["unit"],
                           group=row.get("group") or "Прочее", attributes="")
            s.add(res)
            s.flush()
            resources[res.code] = res
        region = _region(s, row["region"], i)
        zone = _zone(s, region, row.get("zone", ""), i)
        s.add(ReferencePrice(resource_id=res.id, region_id=region.id, zone_id=zone.id if zone else None,
                             dataset_id=dv.id, source=row["source"], quarter=row["quarter"],
                             price=_num(row["price"], i, "price"), doc_ref=row.get("doc_ref", ""),
                             doc_url=row.get("doc_url", "")))
    s.flush()
    return dv


def import_indexes(s: Session, data: bytes, file_name: str, is_demo: bool = False, note: str = "") -> DatasetVersion:
    rows = _rows(data)
    dv = _new_version(s, "indexes", file_name, data, len(rows), is_demo, note)
    for i, row in enumerate(rows, start=2):
        _need(row, ["region", "group", "quarter", "value"], i)
        region = _region(s, row["region"], i)
        existing = s.scalar(select(PriceIndex).where(PriceIndex.region_id == region.id,
                                                     PriceIndex.group == row["group"],
                                                     PriceIndex.quarter == row["quarter"]))
        if existing:
            existing.value, existing.dataset_id = _num(row["value"], i, "value"), dv.id
        else:
            s.add(PriceIndex(region_id=region.id, group=row["group"], quarter=row["quarter"],
                             value=_num(row["value"], i, "value"), dataset_id=dv.id))
    s.flush()
    return dv


def import_analogs(s: Session, data: bytes, file_name: str, is_demo: bool = False, note: str = "") -> DatasetVersion:
    rows = _rows(data)
    dv = _new_version(s, "analogs", file_name, data, len(rows), is_demo, note)
    grouped: dict[tuple, dict] = {}
    for i, row in enumerate(rows, start=2):
        _need(row, ["region", "object_type", "name", "capacity", "ksr_code", "consumption_per_m2"], i)
        key = (row["region"], row["object_type"], row.get("doc_ref") or row["name"])
        obj = grouped.setdefault(key, {"row": row, "line": i, "cons": {}})
        obj["cons"][row["ksr_code"]] = _num(row["consumption_per_m2"], i, "consumption_per_m2")
    for (region_name, otype, ref), obj in grouped.items():
        row = obj["row"]
        s.add(AnalogObject(region_id=_region(s, region_name, obj["line"]).id, object_type=otype,
                           name=row["name"], capacity=_num(row["capacity"], obj["line"], "capacity"),
                           consumption=obj["cons"], doc_ref=ref, dataset_id=dv.id))
    s.flush()
    return dv


def load_directory(s: Session, folder: Path, is_demo: bool) -> None:
    note = "Синтетические данные для демонстрации прототипа" if is_demo else ""
    for name, fn in (("resources.csv", import_resources), ("zones.csv", import_zones)):
        if (folder / name).exists():
            fn(s, (folder / name).read_bytes())
    for name, fn in (("indexes.csv", import_indexes), ("prices.csv", import_prices),
                     ("analogs.csv", import_analogs)):
        if (folder / name).exists():
            fn(s, (folder / name).read_bytes(), f"{folder.name}/{name}", is_demo, note)


def init_db(load_demo: bool = True) -> None:
    Base.metadata.create_all(engine)
    from ..db import SessionLocal
    with SessionLocal() as s:
        seed_regions(s)
        if load_demo and not s.scalar(select(func.count()).select_from(DatasetVersion)):
            demo = REFERENCE_DIR / "demo"
            if demo.exists():
                load_directory(s, demo, is_demo=True)
        s.commit()
