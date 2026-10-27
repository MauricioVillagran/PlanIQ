"""Proceso worker: toma trabajos de `integration.jobs` y los ejecuta de a uno."""

import logging
import os
import signal
import socket
import threading
import time
from datetime import timedelta

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import get_sessionmaker
from app.modules.jobs import repository
from app.modules.jobs.runner import run_once
from worker.handlers import HANDLERS

logger = logging.getLogger("worker")

STALE_CHECK_SECONDS = 60
_stop = threading.Event()


def _request_stop(signum: int, _frame: object) -> None:
    logger.info("Señal recibida, se detiene al terminar el trabajo en curso", extra={"signal": signum})
    _stop.set()


def main() -> None:
    settings = get_settings()
    setup_logging("worker", settings.log_level)
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    session_factory = get_sessionmaker()
    stale_after = timedelta(minutes=settings.worker_stale_job_minutes)
    logger.info("Worker iniciado", extra={"worker_id": worker_id, "job_types": sorted(HANDLERS)})

    last_stale_check = 0.0
    while not _stop.is_set():
        try:
            if time.monotonic() - last_stale_check >= STALE_CHECK_SECONDS:
                with session_factory.begin() as session:
                    requeued = repository.requeue_stale(session, stale_after)
                if requeued:
                    logger.warning("Trabajos reencolados por falta de latido", extra={"count": requeued})
                last_stale_check = time.monotonic()

            if not run_once(session_factory, HANDLERS, worker_id):
                _stop.wait(settings.worker_poll_seconds)
        except Exception:
            # Base caída u otro error de infraestructura: se reintenta sin botar el proceso.
            logger.exception("Error en el ciclo del worker")
            _stop.wait(max(settings.worker_poll_seconds, 10))

    logger.info("Worker detenido")


if __name__ == "__main__":
    main()
