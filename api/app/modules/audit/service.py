"""Consulta del registro de auditoría: listado general e historial de un registro."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.pagination import Page, PageParams
from app.modules.audit.models import AuditLog
from app.modules.audit.schemas import AuditEntryOut
from app.modules.auth.dependencies import CurrentUser
from app.modules.users.models import User


@dataclass(frozen=True)
class AuditFilters:
    entity: str | None = None
    entity_id: int | None = None
    user_id: int | None = None
    action: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


def _apply(query: Select[AuditLog, str], filters: AuditFilters, viewer: CurrentUser) -> Select[AuditLog, str]:
    if filters.entity:
        query = query.where(AuditLog.entity == filters.entity)
    if filters.entity_id is not None:
        query = query.where(AuditLog.entity_id == filters.entity_id)
    if filters.user_id is not None:
        query = query.where(AuditLog.user_id == filters.user_id)
    if filters.action:
        query = query.where(AuditLog.action == filters.action)
    if filters.date_from:
        query = query.where(AuditLog.occurred_at >= filters.date_from)
    if filters.date_to:
        query = query.where(AuditLog.occurred_at < filters.date_to)
    # Lo que pertenece a una planta solo lo ve quien tiene acceso a ella.
    if viewer.plant_ids is not None:
        query = query.where(or_(AuditLog.plant_id.is_(None), AuditLog.plant_id.in_(viewer.plant_ids)))
    return query


def list_entries(
    session: Session, filters: AuditFilters, params: PageParams, viewer: CurrentUser
) -> Page[AuditEntryOut]:
    base = select(AuditLog, User.username).outerjoin(User, User.id == AuditLog.user_id)
    query = _apply(base, filters, viewer)
    total = session.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = session.execute(
        query.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
    ).all()
    items = [
        AuditEntryOut(
            id=log.id,
            occurred_at=log.occurred_at,
            user_id=log.user_id,
            username=username,
            action=log.action,
            entity=log.entity,
            entity_id=log.entity_id,
            plant_id=log.plant_id,
            changes=log.changes,
            request_id=log.request_id,
        )
        for log, username in rows
    ]
    return Page.build(items, params, total=int(total))


def record_history(
    session: Session, entity: str, entity_id: int, params: PageParams, viewer: CurrentUser
) -> Page[AuditEntryOut]:
    """Historial de un registro, para la pestaña "Historial" de cada mantenedor."""
    return list_entries(session, AuditFilters(entity=entity, entity_id=entity_id), params, viewer)
