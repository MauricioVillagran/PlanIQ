"""Operaciones sobre la cola de trabajos. Cada función trabaja dentro de la transacción de quien la llama."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, text, update
from sqlalchemy.orm import Session

from app.modules.jobs.models import Job, JobStatus


@dataclass(frozen=True)
class ClaimedJob:
    id: int
    job_type: str
    plant_id: int | None
    payload: dict[str, Any]
    attempt: int
    max_attempts: int


def enqueue(
    session: Session,
    job_type: str,
    payload: dict[str, Any] | None = None,
    *,
    plant_id: int | None = None,
    created_by: int | None = None,
    priority: int = 0,
    max_attempts: int = 3,
    run_after: datetime | None = None,
) -> Job:
    job = Job(
        job_type=job_type,
        payload=payload,
        plant_id=plant_id,
        created_by=created_by,
        priority=priority,
        max_attempts=max_attempts,
    )
    if run_after is not None:
        job.run_after = run_after
    session.add(job)
    session.flush()
    return job


# UPDLOCK + READPAST: varios workers pueden tomar trabajos a la vez sin tomar el mismo ni bloquearse.
_CLAIM_SQL = text(
    """
    UPDATE j
       SET status = 'running',
           attempts = j.attempts + 1,
           started_at = SYSUTCDATETIME(),
           heartbeat_at = SYSUTCDATETIME(),
           locked_by = :worker_id,
           error = NULL
    OUTPUT inserted.id, inserted.job_type, inserted.plant_id, inserted.payload,
           inserted.attempts, inserted.max_attempts
      FROM integration.jobs AS j
     WHERE j.id = (
           SELECT TOP (1) id
             FROM integration.jobs WITH (UPDLOCK, READPAST, ROWLOCK)
            WHERE status = 'pending' AND run_after <= SYSUTCDATETIME()
            ORDER BY priority DESC, id
     )
    """
)


def claim_next(session: Session, worker_id: str) -> ClaimedJob | None:
    row = session.execute(_CLAIM_SQL, {"worker_id": worker_id}).first()
    if row is None:
        return None
    return ClaimedJob(
        id=row.id,
        job_type=row.job_type,
        plant_id=row.plant_id,
        payload=json.loads(row.payload) if row.payload else {},
        attempt=row.attempts,
        max_attempts=row.max_attempts,
    )


def report_progress(session: Session, job_id: int, progress: Decimal, message: str | None = None) -> None:
    session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(progress=progress, progress_message=message, heartbeat_at=func.sysutcdatetime())
        .execution_options(synchronize_session=False)
    )


def mark_succeeded(session: Session, job_id: int, result: dict[str, Any] | None = None) -> None:
    session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(
            status=JobStatus.SUCCEEDED.value,
            progress=Decimal(100),
            result=result,
            finished_at=func.sysutcdatetime(),
            locked_by=None,
        )
        .execution_options(synchronize_session=False)
    )


def mark_failed(session: Session, job_id: int, error: str, retry_at: datetime | None) -> None:
    """Registra el error. Con `retry_at` el trabajo vuelve a la cola; sin él queda fallido."""
    values: dict[str, Any] = {"error": error, "locked_by": None}
    if retry_at is None:
        values |= {"status": JobStatus.FAILED.value, "finished_at": func.sysutcdatetime()}
    else:
        values |= {"status": JobStatus.PENDING.value, "run_after": retry_at}
    session.execute(
        update(Job).where(Job.id == job_id).values(**values).execution_options(synchronize_session=False)
    )


def requeue_stale(session: Session, stale_after: timedelta) -> int:
    """Devuelve a la cola los trabajos `running` sin latido reciente (worker caído a mitad de un trabajo)."""
    cutoff = datetime.now(UTC) - stale_after
    result = session.execute(
        update(Job)
        .where(Job.status == JobStatus.RUNNING.value, Job.heartbeat_at < cutoff)
        .values(
            status=JobStatus.PENDING.value, locked_by=None, error="Reencolado: el worker dejó de responder"
        )
        .execution_options(synchronize_session=False)
    )
    return int(result.rowcount)  # type: ignore[attr-defined]
