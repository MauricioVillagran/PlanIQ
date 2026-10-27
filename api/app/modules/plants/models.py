"""Plantas. La tabla se crea en F0.4 porque el acceso por planta la necesita; el mantenedor llega en F0.7."""

from enum import StrEnum

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import ActiveMixin, AuditMixin, IdMixin, RowVersionMixin


class PlantType(StrEnum):
    OWN = "own"
    CONTRACT = "contract"  # maquila


class Plant(IdMixin, AuditMixin, ActiveMixin, RowVersionMixin, Base):
    __tablename__ = "plants"
    __table_args__ = (
        CheckConstraint("plant_type IN ('own', 'contract')", name="plant_type"),
        {"schema": "master"},
    )

    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    plant_type: Mapped[str] = mapped_column(String(20), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="America/Santiago")
