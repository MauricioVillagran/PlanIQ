"""Ejecución de trabajos de la cola. Lo usa el proceso worker; vive aquí para poder probarlo con la API."""

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.modules.jobs import repository
from app.modules.jobs.repository import ClaimedJob

logger = logging.getLogger(__name__)

RETRY_BASE_DELAY = timedelta(seconds=30)
RETRY_MAX_DELAY = timedelta(minutes=15)


class PermanentJobError(Exception):
    """Error que no se resuelve reintentando (datos inválidos, archivo con otra estructura, etc.)."""


@dataclass
class JobContext:
    job: ClaimedJob
    _session_factory: sessionmaker[Session]

    def report_progress(self, percent: float | Decimal, message: str | None = None) -> None:
        """Actualiza el avance (0 a 100) en su propia transacción, visible de inmediato en la API."""
        value = max(Decimal(0), min(Decimal(100), Decimal(str(percent)))).quantize(Decimal("0.01"))
        with self._session_factory.begin() as session:
            repository.report_progress(session, self.job.id, value, message)


JobHandler = Callable[[JobContext], dict[str, Any] | None]


def retry_delay(attempt: int) -> timedelta:
    """Espera antes del reintento: 30 s, 60 s, 120 s... con tope de 15 minutos."""
    return min(RETRY_BASE_DELAY * (1 << max(attempt - 1, 0)), RETRY_MAX_DELAY)


def run_once(
    session_factory: sessionmaker[Session], handlers: Mapping[str, JobHandler], worker_id: str
) -> bool:
    """Toma y ejecuta un trabajo. Devuelve False si no había trabajos pendientes."""
    with session_factory.begin() as session:
        job = repository.claim_next(session, worker_id)
    if job is None:
        return False

    log_extra = {"job_id": job.id, "job_type": job.job_type, "attempt": job.attempt}
    handler = handlers.get(job.job_type)
    if handler is None:
        logger.error("Tipo de trabajo desconocido", extra=log_extra)
        with session_factory.begin() as session:
            repository.mark_failed(session, job.id, f"Tipo de trabajo desconocido: {job.job_type}", None)
        return True

    logger.info("Trabajo iniciado", extra=log_extra)
    try:
        result = handler(JobContext(job, session_factory))
    except PermanentJobError as exc:
        logger.warning("Trabajo fallido sin reintento: %s", exc, extra=log_extra)
        with session_factory.begin() as session:
            repository.mark_failed(session, job.id, str(exc), None)
    except Exception as exc:
        retry_at = datetime.now(UTC) + retry_delay(job.attempt) if job.attempt < job.max_attempts else None
        logger.exception("Trabajo con error", extra=log_extra | {"retry": retry_at is not None})
        with session_factory.begin() as session:
            repository.mark_failed(session, job.id, f"{type(exc).__name__}: {exc}", retry_at)
    else:
        with session_factory.begin() as session:
            repository.mark_succeeded(session, job.id, result)
        logger.info("Trabajo terminado", extra=log_extra)
    return True
