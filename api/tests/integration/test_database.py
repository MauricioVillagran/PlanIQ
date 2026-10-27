from datetime import UTC, datetime

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import Connection, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.db.migration_support import compare_type
from app.db.models import Base
from app.modules.jobs import repository
from app.modules.jobs.models import Job

pytestmark = pytest.mark.integration


def test_migrations_match_models(connection: Connection) -> None:
    ctx = MigrationContext.configure(connection, opts={"include_schemas": True, "compare_type": compare_type})
    diffs = [
        d
        for d in compare_metadata(ctx, Base.metadata)
        # La tabla de versiones de Alembic no es un modelo.
        if not (d[0] == "remove_table" and d[1].name == "alembic_version")
    ]
    assert diffs == []


def test_schemas_exist(connection: Connection) -> None:
    names = set(connection.execute(text("SELECT name FROM sys.schemas")).scalars())
    assert {"core", "master", "plan", "actual", "integration"} <= names


def test_utc_datetime_roundtrip_is_timezone_aware(db_session: Session) -> None:
    job = repository.enqueue(db_session, "system.noop")
    db_session.refresh(job)
    assert job.created_at.tzinfo is UTC
    assert abs((datetime.now(UTC) - job.created_at).total_seconds()) < 60


def test_rowversion_detects_concurrent_update(db_session: Session, connection: Connection) -> None:
    job = repository.enqueue(db_session, "system.noop")
    original_version = job.row_version
    assert isinstance(original_version, bytes) and len(original_version) == 8

    # Otro usuario modifica la misma fila: cambia su rowversion.
    connection.execute(text("UPDATE integration.jobs SET priority = 5 WHERE id = :id"), {"id": job.id})

    job.priority = 9
    with pytest.raises(StaleDataError):
        db_session.flush()


def test_rowversion_is_refreshed_after_own_update(db_session: Session) -> None:
    job = repository.enqueue(db_session, "system.noop")
    before = job.row_version
    job.priority = 1
    db_session.flush()
    assert job.row_version != before


def test_readiness_reports_database_and_schema_revision(client: TestClient) -> None:
    res = client.get("/api/v1/health/ready")
    assert res.status_code == 200
    body = res.json()
    assert body["database"] == "ok"
    assert body["schema_revision"] == "0005"


def test_openapi_is_served(client: TestClient) -> None:
    res = client.get("/api/v1/openapi.json")
    assert res.status_code == 200
    assert res.json()["info"]["title"] == "PlanIQ API"


def test_job_model_is_registered() -> None:
    assert "integration.jobs" in Base.metadata.tables
    assert Base.metadata.tables["integration.jobs"] is Job.__table__
