"""Plan diario de cosecha (secciones 5.2 y 6, ADR 0005).

Un plan por planta y fecha productiva, con sus líneas de cosecha. `daily_plans` y `harvest_entries` son
tablas temporales de SQL Server: el motor guarda cada estado anterior en el esquema `plan_history` y el
plan se puede leer "tal como estaba" con `FOR SYSTEM_TIME AS OF` (ver repository.entries_as_of). Las
columnas de período (`valid_from`, `valid_to`) son ocultas y no se mapean: las administra el motor.

`daily_plan_versions` es solo la cabecera de cada versión publicada (número, motivo, usuario) con el
instante que la reconstruye desde el historial.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin, IdMixin, RowVersionMixin
from app.db.types import PreciseUtcDateTime, UtcDateTime
from app.domain.harvest import biomass_kg
from app.modules.farms.models import Cage, FarmCenter, HoldingCage
from app.modules.shifts.models import Shift


class PlanStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"


class VersionKind(StrEnum):
    PUBLISH = "publish"  # primera publicación (versión 1)
    CHANGE = "change"  # lote de cambios con motivo sobre un plan publicado


class DailyPlan(IdMixin, AuditMixin, RowVersionMixin, Base):
    __tablename__ = "daily_plans"
    __table_args__ = (
        UniqueConstraint("plant_id", "productive_date", name="uq_daily_plans_plant_id_productive_date"),
        CheckConstraint("status IN ('draft', 'published', 'closed')", name="status"),
        {"schema": "plan"},
    )

    plant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("master.plants.id"), nullable=False)
    productive_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PlanStatus.DRAFT)
    # Versión vigente: 0 mientras es Borrador; 1 al publicar; +1 por cada lote de cambios.
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    published_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    published_by: Mapped[int | None] = mapped_column(BigInteger)
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    closed_by: Mapped[int | None] = mapped_column(BigInteger)

    entries: Mapped[list["HarvestEntry"]] = relationship(
        back_populates="daily_plan", order_by="HarvestEntry.sequence", cascade="all, delete-orphan"
    )


class HarvestEntry(IdMixin, AuditMixin, RowVersionMixin, Base):
    """Una línea del plan de cosecha. Se borra de verdad: su historia queda en la tabla temporal."""

    __tablename__ = "harvest_entries"
    __table_args__ = (
        CheckConstraint("fish_count > 0", name="fish_count"),
        CheckConstraint("avg_weight_kg > 0", name="avg_weight_kg"),
        CheckConstraint("sequence > 0", name="sequence"),
        Index("ix_harvest_entries_daily_plan_id_sequence", "daily_plan_id", "sequence"),
        {"schema": "plan"},
    )

    plant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("master.plants.id"), nullable=False)
    daily_plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plan.daily_plans.id"), nullable=False)
    farm_center_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("master.farm_centers.id"), nullable=False
    )
    cage_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("master.cages.id"), nullable=False)
    holding_cage_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("master.holding_cages.id"), nullable=False
    )
    shift_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("master.shifts.id"), nullable=False)
    fish_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_weight_kg: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    # Orden de faena dentro del día: 1, 2, 3...
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))

    daily_plan: Mapped[DailyPlan] = relationship(back_populates="entries")
    farm_center: Mapped[FarmCenter] = relationship(lazy="joined")
    cage: Mapped[Cage] = relationship(lazy="joined")
    holding_cage: Mapped[HoldingCage] = relationship(lazy="joined")
    shift: Mapped[Shift] = relationship(lazy="joined")

    @property
    def farm_center_code(self) -> str:
        return self.farm_center.code

    @property
    def farm_center_name(self) -> str:
        return self.farm_center.name

    @property
    def cage_code(self) -> str:
        return self.cage.code

    @property
    def holding_cage_code(self) -> str:
        return self.holding_cage.code

    @property
    def shift_name(self) -> str:
        return self.shift.name

    @property
    def biomass_kg(self) -> Decimal:
        return biomass_kg(self.fish_count, self.avg_weight_kg)


class DailyPlanVersion(IdMixin, AuditMixin, Base):
    """Cabecera de una versión publicada. Inmutable: no lleva rowversion ni se edita."""

    __tablename__ = "daily_plan_versions"
    __table_args__ = (
        UniqueConstraint("daily_plan_id", "number", name="uq_daily_plan_versions_daily_plan_id_number"),
        CheckConstraint("kind IN ('publish', 'change')", name="kind"),
        {"schema": "plan"},
    )

    plant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("master.plants.id"), nullable=False)
    daily_plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plan.daily_plans.id"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    # Obligatorio en los cambios sobre un plan publicado; la primera publicación no lo pide.
    reason: Mapped[str | None] = mapped_column(String(500))
    # Instante de SQL Server tomado dentro de la misma transacción que guardó la versión: leer las
    # tablas temporales AS OF este instante devuelve el plan exactamente como quedó en esta versión.
    snapshot_at: Mapped[datetime] = mapped_column(
        PreciseUtcDateTime, nullable=False, server_default=func.sysutcdatetime()
    )
