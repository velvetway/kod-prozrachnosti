"""Модель данных: справочники (регионы, зоны, ресурсы, ориентиры, индексы, аналоги),
данные проверки (проверка, позиции, сопоставления, сигналы) и журнал решений."""
from datetime import datetime

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint, JSON)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


# ---------------------------------------------------------------- справочники
class Region(Base):
    __tablename__ = "region"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    federal_district: Mapped[str] = mapped_column(String(60))
    is_pilot: Mapped[bool] = mapped_column(Boolean, default=False)
    zones: Mapped[list["PriceZone"]] = relationship(back_populates="region", order_by="PriceZone.number")


class PriceZone(Base):
    __tablename__ = "price_zone"
    __table_args__ = (UniqueConstraint("region_id", "number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"))
    number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    region: Mapped[Region] = relationship(back_populates="zones")


class DatasetVersion(Base):
    __tablename__ = "dataset_version"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True)
    kind: Mapped[str] = mapped_column(String(30))          # prices | indexes | analogs
    source_file: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    records: Mapped[int] = mapped_column(Integer)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(Text, default="")
    loaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Resource(Base):
    """Строительный ресурс классификатора (КСР)."""
    __tablename__ = "ksr_resource"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(30))
    group: Mapped[str] = mapped_column(String(60))
    attributes: Mapped[str] = mapped_column(Text, default="")


class ReferencePrice(Base):
    __tablename__ = "reference_price"
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("ksr_resource.id"), index=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"), index=True)
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("price_zone.id"), nullable=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset_version.id"))
    source: Mapped[str] = mapped_column(String(20))        # fgiscs | eis | market
    price: Mapped[float] = mapped_column(Float)            # руб. за единицу ресурса, без НДС
    quarter: Mapped[str] = mapped_column(String(7))        # 2026-Q3
    doc_ref: Mapped[str] = mapped_column(Text, default="")
    doc_url: Mapped[str] = mapped_column(String(500), default="")
    resource: Mapped[Resource] = relationship()
    zone: Mapped[PriceZone | None] = relationship()
    dataset: Mapped[DatasetVersion] = relationship()


class PriceIndex(Base):
    """Индекс цен группы ресурсов к базовому кварталу (базовый = 1.0)."""
    __tablename__ = "price_index"
    __table_args__ = (UniqueConstraint("region_id", "group", "quarter"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"))
    group: Mapped[str] = mapped_column(String(60))
    quarter: Mapped[str] = mapped_column(String(7))
    value: Mapped[float] = mapped_column(Float)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset_version.id"))


class AnalogObject(Base):
    __tablename__ = "analog_object"
    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"))
    object_type: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(Text)
    capacity: Mapped[float] = mapped_column(Float)          # м² (для дорог — м² покрытия)
    consumption: Mapped[dict] = mapped_column(JSON)         # {код КСР: расход на 1 м²}
    doc_ref: Mapped[str] = mapped_column(Text, default="")
    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset_version.id"))


# ---------------------------------------------------------------- проверка
class Check(Base):
    __tablename__ = "check_run"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True)
    title: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64))
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"))
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("price_zone.id"), nullable=True)
    quarter: Mapped[str] = mapped_column(String(7))
    base_quarter: Mapped[str | None] = mapped_column(String(7), nullable=True)
    object_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    capacity: Mapped[float | None] = mapped_column(Float, nullable=True)
    params: Mapped[dict] = mapped_column(JSON)              # пороги, источники
    data_versions: Mapped[dict] = mapped_column(JSON)       # версии справочников
    result_sha256: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(30), default="Ожидает решения")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    region: Mapped[Region] = relationship()
    zone: Mapped[PriceZone | None] = relationship()
    items: Mapped[list["CheckItem"]] = relationship(back_populates="check", order_by="CheckItem.position",
                                                    cascade="all, delete-orphan")


class CheckItem(Base):
    __tablename__ = "check_item"
    id: Mapped[int] = mapped_column(primary_key=True)
    check_id: Mapped[int] = mapped_column(ForeignKey("check_run.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    source_row: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(40), default="")
    name: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    base_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    check: Mapped[Check] = relationship(back_populates="items")
    match: Mapped["Match | None"] = relationship(back_populates="item", uselist=False,
                                                 cascade="all, delete-orphan")
    signals: Mapped[list["Signal"]] = relationship(back_populates="item", cascade="all, delete-orphan",
                                                   order_by="Signal.id")


class Match(Base):
    __tablename__ = "match"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("check_item.id"), unique=True)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("ksr_resource.id"), nullable=True)
    method: Mapped[str] = mapped_column(String(30))         # code | name | manual | none
    score: Mapped[float] = mapped_column(Float)
    level: Mapped[str] = mapped_column(String(20))          # Высокая | Средняя | Низкая | Нет
    unit_factor: Mapped[float] = mapped_column(Float, default=1.0)  # ед. позиции → ед. ресурса
    note: Mapped[str] = mapped_column(Text, default="")
    item: Mapped[CheckItem] = relationship(back_populates="match")
    resource: Mapped[Resource | None] = relationship()


class Signal(Base):
    """Результат расчёта по одному виду контроля для позиции (в том числе без превышения)."""
    __tablename__ = "signal"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("check_item.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))           # price | volume | escalation
    level: Mapped[str] = mapped_column(String(20))          # high | medium | none | review | na
    actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    benchmark: Mapped[float | None] = mapped_column(Float, nullable=True)
    deviation_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    overpay: Mapped[float] = mapped_column(Float, default=0.0)
    formula: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSON)             # источники, коридор, пороги
    item: Mapped[CheckItem] = relationship(back_populates="signals")
    decisions: Mapped[list["Decision"]] = relationship(back_populates="signal", order_by="Decision.id",
                                                       cascade="all, delete-orphan")


class Decision(Base):
    __tablename__ = "decision"
    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signal.id"), index=True)
    outcome: Mapped[str] = mapped_column(String(60))
    comment: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(120), default="Специалист (демо-доступ)")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    signal: Mapped[Signal] = relationship(back_populates="decisions")


# ---------------------------------------------------------------- доступ и аудит
class User(Base):
    __tablename__ = "app_user"
    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))              # specialist | admin
    password_hash: Mapped[str] = mapped_column(String(200))


class SessionToken(Base):
    __tablename__ = "app_session"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    user: Mapped[User] = relationship()


class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    user_login: Mapped[str] = mapped_column(String(60))
    action: Mapped[str] = mapped_column(String(60))
    object_ref: Mapped[str] = mapped_column(String(200), default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
