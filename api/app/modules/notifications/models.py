"""Eventos del plan y avisos internos (sección 6, ADR 0005 decisión 9).

Cada publicación o modificación del plan queda como un evento (`plan.change_events`); de él salen los
avisos de la campana, uno por destinatario (`plan.notifications`). Separar evento y aviso permite
agregar otros canales (correo) sin rediseñar. Ninguna de las dos es temporal (ADR 0001, decisión 4) y
no se auditan fila a fila: son registros del sistema que nadie edita.
"""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import IdMixin
from app.db.types import UtcDateTime


class ChangeEvent(IdMixin, Base):
    __tablename__ = "change_events"
    __table_args__ = (
        CheckConstraint("event_type IN ('plan.published', 'plan.changed', 'plan.closed')", name="event_type"),
        Index("ix_change_events_daily_plan_id", "daily_plan_id"),
        {"schema": "plan"},
    )
    __audit__ = False

    plant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("master.plants.id"), nullable=False)
    daily_plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plan.daily_plans.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    version_number: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(String(500))
    # Null = acción del sistema.
    actor_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, server_default=func.sysutcdatetime()
    )


class Notification(IdMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id_read_at", "user_id", "read_at"),
        {"schema": "plan"},
    )
    __audit__ = False

    plant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("master.plants.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("core.users.id"), nullable=False)
    change_event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("plan.change_events.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(String(600))
    # Ruta interna de la aplicación, con planta y fecha en la URL.
    link: Mapped[str | None] = mapped_column(String(300))
    read_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, server_default=func.sysutcdatetime()
    )
