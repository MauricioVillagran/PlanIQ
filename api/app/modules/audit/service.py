"""Consulta del registro de auditoría: listado general e historial de un registro."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError
from app.core.pagination import Page, PageParams
from app.modules.audit.labels import entity_label
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
            entity_label=entity_label(log.entity),
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


MAX_EXPORT_ROWS = 50_000


def export_entries(
    session: Session, filters: AuditFilters, viewer: CurrentUser
) -> list[tuple[AuditLog, str | None]]:
    """Las entradas filtradas para Excel, más recientes primero, con el mismo alcance por planta."""
    base = select(AuditLog, User.username).outerjoin(User, User.id == AuditLog.user_id)
    query = _apply(base, filters, viewer).order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
    rows = session.execute(query.limit(MAX_EXPORT_ROWS + 1)).all()
    if len(rows) > MAX_EXPORT_ROWS:
        raise BusinessRuleError(
            "La exportación supera 50.000 filas. Acote las fechas o los filtros.", code="export_too_large"
        )
    return [(log, username) for log, username in rows]


def _scoped(query: Select[Any], viewer: CurrentUser) -> Select[Any]:
    if viewer.plant_ids is not None:
        query = query.where(or_(AuditLog.plant_id.is_(None), AuditLog.plant_id.in_(viewer.plant_ids)))
    return query


def distinct_entities(session: Session, viewer: CurrentUser) -> list[str]:
    """Tablas con al menos un registro visible, para el filtro."""
    return list(
        session.scalars(_scoped(select(AuditLog.entity).distinct(), viewer).order_by(AuditLog.entity))
    )


def distinct_users(session: Session, viewer: CurrentUser) -> list[tuple[int, str, str]]:
    """Usuarios que aparecen en la auditoría visible (id, usuario, nombre), para el filtro."""
    ids = _scoped(select(AuditLog.user_id).where(AuditLog.user_id.is_not(None)).distinct(), viewer)
    rows = session.execute(
        select(User.id, User.username, User.full_name).where(User.id.in_(ids)).order_by(User.username)
    ).all()
    return [(row.id, row.username, row.full_name) for row in rows]
