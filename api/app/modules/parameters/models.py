"""Parámetros configurables con tipo, unidad, alcance (global o por planta) y vigencia."""

from datetime import date
from enum import StrEnum

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import ActiveMixin, AuditMixin, IdMixin, RowVersionMixin


class ValueType(StrEnum):
    INT = "int"
    DECIMAL = "decimal"
    BOOL = "bool"
    TEXT = "text"


class Parameter(IdMixin, AuditMixin, ActiveMixin, RowVersionMixin, Base):
    __tablename__ = "parameters"
    __table_args__ = (
        CheckConstraint("value_type IN ('int', 'decimal', 'bool', 'text')", name="value_type"),
        CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_from < valid_to", name="validity"),
        Index("ix_parameters_key_plant_id", "key", "plant_id"),
        {"schema": "master"},
    )

    # Clave estable, en minúsculas con puntos: "shifts.full_coverage", "harvest.avg_weight_kg.max".
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    # Null = valor global; un valor de la planta lo reemplaza para esa planta.
    plant_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("master.plants.id"))
    value_type: Mapped[str] = mapped_column(String(10), nullable=False)
    # Texto normalizado según el tipo ("1.5", "true", "12").
    value: Mapped[str] = mapped_column(String(400), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(String(400))
    # Vigencia [desde, hasta); null = sin límite.
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
