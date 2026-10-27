"""Turnos por planta. La regla de fecha productiva está en app.domain.shifts."""

from datetime import time

from sqlalchemy import BigInteger, Boolean, ForeignKey, SmallInteger, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import ActiveMixin, AuditMixin, IdMixin, RowVersionMixin
from app.domain.shifts import ShiftWindow


class Shift(IdMixin, AuditMixin, ActiveMixin, RowVersionMixin, Base):
    __tablename__ = "shifts"
    __table_args__ = (
        UniqueConstraint("plant_id", "name", name="uq_shifts_plant_id_name"),
        {"schema": "master"},
    )

    plant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("master.plants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    # Hora local de la planta.
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    # Calculado al guardar (término <= inicio).
    crosses_midnight: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0", default=0)

    def window(self) -> ShiftWindow:
        return ShiftWindow(self.name, self.start_time, self.end_time)

    @property
    def duration_minutes(self) -> int:
        return self.window().duration_minutes
