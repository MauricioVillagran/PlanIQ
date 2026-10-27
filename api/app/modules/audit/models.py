"""Registro central de auditoría: toda creación, modificación, desactivación y borrado hecho por el ORM."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, BigInteger, CheckConstraint, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import IdMixin
from app.db.types import UtcDateTime


class AuditAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DEACTIVATE = "deactivate"
    ACTIVATE = "activate"
    DELETE = "delete"


class AuditLog(IdMixin, Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint("action IN ('create', 'update', 'deactivate', 'activate', 'delete')", name="action"),
        Index("ix_audit_log_entity_entity_id_occurred_at", "entity", "entity_id", "occurred_at"),
        Index("ix_audit_log_user_id_occurred_at", "user_id", "occurred_at"),
        Index("ix_audit_log_occurred_at", "occurred_at"),
        {"schema": "core"},
    )
    # El propio registro de auditoría no se audita.
    __audit__ = False

    occurred_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, server_default=func.sysutcdatetime()
    )
    # Null = acción del sistema (worker, arranque, intentos de ingreso anónimos).
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    # Nombre completo de la tabla, por ejemplo "master.plants".
    entity: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    plant_id: Mapped[int | None] = mapped_column(BigInteger)
    # {campo: {"old": ..., "new": ...}}; en relaciones {campo: {"added": [...], "removed": [...]}}.
    changes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64))
