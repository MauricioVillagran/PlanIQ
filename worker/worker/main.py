"""Esqueleto mínimo del worker para verificar la infraestructura (F0.2).

Confirma que arranca, que llega a la base y que ve los archivos montados. La cola de trabajos
(`integration.jobs`) llega en F0.3.
"""

import logging
import os
import signal
import threading
from pathlib import Path

from app.db import odbc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s worker %(message)s")
logger = logging.getLogger("worker")

HEARTBEAT_SECONDS = 60
_stop = threading.Event()


def _request_stop(signum: int, _frame: object) -> None:
    logger.info("Señal %s recibida, deteniendo", signum)
    _stop.set()


def main() -> None:
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    try:
        logger.info("Conectado a SQL Server %s", odbc.ping())
    except Exception:
        logger.exception("No se pudo conectar a la base")

    samples_dir = os.environ.get("SAMPLE_FILES_PATH")
    if samples_dir and Path(samples_dir).is_dir():
        count = sum(1 for p in Path(samples_dir).iterdir() if p.is_file())
        logger.info("Carpeta de archivos de ejemplo montada en %s (%d archivos, solo lectura)", samples_dir, count)

    while not _stop.wait(HEARTBEAT_SECONDS):
        logger.info("Activo")


if __name__ == "__main__":
    main()
