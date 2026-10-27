"""Cola de trabajos persistida en SQL Server (sin Redis): `integration.jobs`."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, BigInteger, CheckConstraint, Index, Numeric, SmallInteger, String, func
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin, IdMixin, RowVersionMixin
from app.db.types import UtcDateTime


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(IdMixin, AuditMixin, RowVersionMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')", name="status"
        ),
        CheckConstraint("progress >= 0 AND progress <= 100", name="progress"),
        CheckConstraint("attempts >= 0 AND max_attempts >= 1", name="attempts"),
        # Búsqueda del siguiente trabajo pendiente.
        Index("ix_jobs_status_run_after", "status", "run_after", "priority"),
        {"schema": "integration"},
    )

    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=JobStatus.PENDING.value)
    # Planta a la que pertenece el trabajo, si aplica (FK a master.plants cuando exista la tabla).
    plant_id: Mapped[int | None] = mapped_column(BigInteger)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    progress: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    progress_message: Mapped[str | None] = mapped_column(String(400))
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="3")
    run_after: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, server_default=func.sysutcdatetime()
    )
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    locked_by: Mapped[str | None] = mapped_column(String(100))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(mssql.NVARCHAR(None))
