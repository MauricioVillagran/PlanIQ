"""Estado del servicio para Docker, el proxy y el monitoreo."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.errors import AppError
from app.db.session import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    sqlserver_version: str
    schema_revision: str | None


class DatabaseUnavailableError(AppError):
    status_code = 503
    code = "database_unavailable"
    message = "La base de datos no responde."


@router.get("", response_model=HealthResponse, summary="Liveness: el proceso responde")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness: la base responde")
def ready(session: SessionDep) -> ReadinessResponse:
    try:
        version = session.execute(
            text("SELECT CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(32))")
        ).scalar()
        revision = session.execute(
            text("SELECT TOP (1) version_num FROM dbo.alembic_version")
        ).scalar_one_or_none()
    except Exception as exc:
        logger.exception("No se pudo consultar la base")
        raise DatabaseUnavailableError from exc
    return ReadinessResponse(
        status="ok", database="ok", sqlserver_version=str(version), schema_revision=revision
    )
