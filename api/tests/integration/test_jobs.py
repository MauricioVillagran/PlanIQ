from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.modules.jobs import repository
from app.modules.jobs.models import Job, JobStatus
from app.modules.jobs.runner import JobContext, PermanentJobError, run_once

pytestmark = pytest.mark.integration

WORKER = "test-worker:1"


def _reload(session: Session, job_id: int) -> Job:
    session.expire_all()
    job = session.get(Job, job_id)
    assert job is not None
    return job


def test_claim_returns_none_when_queue_is_empty(db_session: Session) -> None:
    assert repository.claim_next(db_session, WORKER) is None


def test_claim_takes_highest_priority_then_oldest(db_session: Session) -> None:
    low = repository.enqueue(db_session, "a", {"n": 1})
    high = repository.enqueue(db_session, "b", {"n": 2}, priority=5)
    db_session.flush()

    first = repository.claim_next(db_session, WORKER)
    second = repository.claim_next(db_session, WORKER)

    assert first is not None and second is not None
    assert (first.id, second.id) == (high.id, low.id)
    assert first.payload == {"n": 2}
    assert first.attempt == 1
    assert repository.claim_next(db_session, WORKER) is None


def test_claim_skips_jobs_scheduled_for_later(db_session: Session) -> None:
    repository.enqueue(db_session, "a", run_after=datetime.now(UTC) + timedelta(hours=1))
    assert repository.claim_next(db_session, WORKER) is None


def test_successful_job_stores_result_and_progress(
    db_session: Session, session_factory: sessionmaker[Session]
) -> None:
    job_id = repository.enqueue(db_session, "echo", {"x": 1}).id
    db_session.commit()
    seen_progress: list[Decimal] = []

    def echo(ctx: JobContext) -> dict[str, Any]:
        ctx.report_progress(40, "Mitad")
        with session_factory() as s:
            seen_progress.append(_reload(s, ctx.job.id).progress)
        return {"echo": ctx.job.payload}

    assert run_once(session_factory, {"echo": echo}, WORKER) is True

    job = _reload(db_session, job_id)
    assert seen_progress == [Decimal("40.00")]
    assert job.status == JobStatus.SUCCEEDED
    assert job.progress == Decimal(100)
    assert job.result == {"echo": {"x": 1}}
    assert job.finished_at is not None
    assert job.locked_by is None


def test_failed_job_is_retried_later_then_marked_failed(
    db_session: Session, session_factory: sessionmaker[Session]
) -> None:
    job_id = repository.enqueue(db_session, "boom", max_attempts=2).id
    db_session.commit()

    def boom(_ctx: JobContext) -> None:
        raise RuntimeError("archivo ilegible")

    run_once(session_factory, {"boom": boom}, WORKER)
    job = _reload(db_session, job_id)
    assert job.status == JobStatus.PENDING
    assert job.attempts == 1
    assert job.run_after > datetime.now(UTC)
    assert job.error == "RuntimeError: archivo ilegible"

    # Se adelanta el reintento para no esperar.
    db_session.execute(
        update(Job).where(Job.id == job_id).values(run_after=datetime.now(UTC) - timedelta(seconds=5))
    )
    db_session.commit()
    run_once(session_factory, {"boom": boom}, WORKER)

    job = _reload(db_session, job_id)
    assert job.status == JobStatus.FAILED
    assert job.attempts == 2
    assert job.finished_at is not None


def test_permanent_error_is_not_retried(db_session: Session, session_factory: sessionmaker[Session]) -> None:
    job_id = repository.enqueue(db_session, "bad", max_attempts=5).id
    db_session.commit()

    def bad(_ctx: JobContext) -> None:
        raise PermanentJobError("Faltan columnas: peso_entrada")

    run_once(session_factory, {"bad": bad}, WORKER)
    job = _reload(db_session, job_id)
    assert job.status == JobStatus.FAILED
    assert job.error == "Faltan columnas: peso_entrada"


def test_unknown_job_type_fails_without_retry(
    db_session: Session, session_factory: sessionmaker[Session]
) -> None:
    job_id = repository.enqueue(db_session, "no.registrado").id
    db_session.commit()

    run_once(session_factory, {}, WORKER)
    job = _reload(db_session, job_id)
    assert job.status == JobStatus.FAILED
    assert "desconocido" in (job.error or "")


def test_stale_running_jobs_are_requeued(db_session: Session) -> None:
    job_id = repository.enqueue(db_session, "a").id
    repository.claim_next(db_session, WORKER)
    db_session.execute(
        update(Job).where(Job.id == job_id).values(heartbeat_at=datetime.now(UTC) - timedelta(hours=1))
    )

    assert repository.requeue_stale(db_session, timedelta(minutes=15)) == 1
    job = _reload(db_session, job_id)
    assert job.status == JobStatus.PENDING
    assert job.locked_by is None
