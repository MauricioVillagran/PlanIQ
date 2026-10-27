"""Registro de tipos de trabajo que ejecuta el worker.

Cada fase agrega aquí sus trabajos (cargas Excel, sincronización con Innova, recálculo de perfiles).
"""

from typing import Any

from app.modules.jobs.runner import JobContext, JobHandler


def noop(ctx: JobContext) -> dict[str, Any]:
    """Trabajo de prueba: verifica de punta a punta que la cola y el worker funcionan."""
    ctx.report_progress(50, "Procesando")
    return {"echo": ctx.job.payload}


HANDLERS: dict[str, JobHandler] = {
    "system.noop": noop,
}
