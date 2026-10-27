"""Maestros de cultivo (sección 5.1): centros, jaulas y jaulas de acopio.

Centros y jaulas son globales: un centro puede despachar a varias plantas. Las jaulas de acopio son de
cada planta (ADR 0005, decisión 6).
"""

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import ActiveMixin, AuditMixin, IdMixin, RowVersionMixin
from app.modules.plants.models import Plant


class FarmCenter(IdMixin, AuditMixin, ActiveMixin, RowVersionMixin, Base):
    __tablename__ = "farm_centers"
    __table_args__ = {"schema": "master"}

    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    # Zona o barrio de salmonicultura.
    zone: Mapped[str | None] = mapped_column(String(100))


class Cage(IdMixin, AuditMixin, ActiveMixin, RowVersionMixin, Base):
    __tablename__ = "cages"
    __table_args__ = (
        UniqueConstraint("farm_center_id", "code", name="uq_cages_farm_center_id_code"),
        {"schema": "master"},
    )

    farm_center_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("master.farm_centers.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)

    farm_center: Mapped[FarmCenter] = relationship(lazy="joined")

    @property
    def farm_center_code(self) -> str:
        return self.farm_center.code

    @property
    def farm_center_name(self) -> str:
        return self.farm_center.name


class HoldingCage(IdMixin, AuditMixin, ActiveMixin, RowVersionMixin, Base):
    __tablename__ = "holding_cages"
    __table_args__ = (
        UniqueConstraint("plant_id", "code", name="uq_holding_cages_plant_id_code"),
        CheckConstraint("capacity_fish > 0", name="capacity_fish"),
        {"schema": "master"},
    )

    plant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("master.plants.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    # Capacidad en peces: la suma por turno en el plan no puede superarla (ADR 0005, decisión 3).
    capacity_fish: Mapped[int] = mapped_column(Integer, nullable=False)

    plant: Mapped[Plant] = relationship(lazy="joined")
