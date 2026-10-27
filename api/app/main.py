"""Esqueleto mínimo de la API para verificar la infraestructura (F0.2).

F0.3 incorpora configuración, logging estructurado, formato de errores, SQLAlchemy y Alembic.
"""

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.db import odbc

logger = logging.getLogger(__name__)

app = FastAPI(
    title="PlanIQ API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/v1/openapi.json",
)


@app.get("/api/v1/health", tags=["health"])
def health() -> dict[str, str]:
    """Liveness: el proceso responde. No consulta la base."""
    return {"status": "ok"}


@app.get("/api/v1/health/ready", tags=["health"])
def ready() -> JSONResponse:
    """Readiness: la API puede conectarse a SQL Server."""
    try:
        version = odbc.ping()
    except Exception:
        logger.exception("No se pudo conectar a la base")
        return JSONResponse(status_code=503, content={"status": "error", "database": "unreachable"})
    return JSONResponse(content={"status": "ok", "database": "ok", "sqlserver_version": version})
