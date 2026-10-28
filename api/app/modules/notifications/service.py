"""Eventos del plan y avisos de la campana.

Destinatarios (ADR 0005, decisión 9): usuarios activos con `plan.view` y acceso a la planta, excepto
quien hizo el cambio.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ColumnElement, Exists, exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams
from app.modules.daily_plans.models import DailyPlan
from app.modules.notifications.models import ChangeEvent, Notification
from app.modules.notifications.schemas import NotificationOut, NotificationSummaryOut
from app.modules.parameters.values import get_parameter
from app.modules.roles.models import Permission, RolePermission
from app.modules.users.models import User, UserPlant, UserRole

POLL_PARAMETER = "notifications.poll_seconds"
# Sin el parámetro, un minuto: el mínimo del rango de polling del proyecto (1 a 5 minutos).
DEFAULT_POLL_SECONDS = 60

_TITLES = {
    "plan.published": "Plan del {day} publicado",
    "plan.changed": "Plan del {day} modificado (versión {version})",
}


def _has_permission(code: str) -> Exists:
    return exists(
        select(1)
        .select_from(UserRole)
        .join(RolePermission, RolePermission.role_id == UserRole.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(UserRole.user_id == User.id, Permission.code == code)
    )


def recipients(session: Session, plant_id: int, exclude_user_id: int | None) -> list[int]:
    plant_access = exists(select(1).where(UserPlant.user_id == User.id, UserPlant.plant_id == plant_id))
    query = select(User.id).where(
        User.is_active,
        _has_permission("plan.view"),
        or_(plant_access, _has_permission("plants.all")),
    )
    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)
    return list(session.scalars(query))


def notify_plan_event(
    session: Session,
    plan: DailyPlan,
    event_type: str,
    *,
    actor_id: int | None,
    reason: str | None = None,
) -> ChangeEvent:
    """Registra el evento y crea un aviso por destinatario, en la misma transacción del cambio."""
    event = ChangeEvent(
        plant_id=plan.plant_id,
        daily_plan_id=plan.id,
        event_type=event_type,
        version_number=plan.current_version or None,
        reason=reason,
        actor_id=actor_id,
    )
    session.add(event)
    session.flush()
    actor = session.get(User, actor_id) if actor_id is not None else None
    title = _TITLES[event_type].format(
        day=plan.productive_date.strftime("%d-%m-%Y"), version=plan.current_version
    )
    body = " · ".join(part for part in (f"Por {actor.full_name}" if actor else None, reason) if part)
    link = f"/plan?plant={plan.plant_id}&date={plan.productive_date.isoformat()}"
    for user_id in recipients(session, plan.plant_id, actor_id):
        session.add(
            Notification(
                plant_id=plan.plant_id,
                user_id=user_id,
                change_event_id=event.id,
                title=title,
                body=body or None,
                link=link,
            )
        )
    return event


def _mine(user_id: int, plant_ids: frozenset[int] | None) -> list[ColumnElement[bool]]:
    """Los avisos del usuario, solo de las plantas a las que hoy tiene acceso."""
    conditions = [Notification.user_id == user_id]
    if plant_ids is not None:
        conditions.append(Notification.plant_id.in_(plant_ids))
    return conditions


def list_notifications(
    session: Session, user_id: int, plant_ids: frozenset[int] | None, params: PageParams, unread_only: bool
) -> Page[NotificationOut]:
    query = select(Notification).where(*_mine(user_id, plant_ids))
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
    ).all()
    return Page.build([NotificationOut.model_validate(n) for n in rows], params, total=int(total))


def _poll_seconds(session: Session) -> int:
    value: Any = get_parameter(session, POLL_PARAMETER)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return DEFAULT_POLL_SECONDS


def summary(session: Session, user_id: int, plant_ids: frozenset[int] | None) -> NotificationSummaryOut:
    unread = session.scalar(
        select(func.count(Notification.id)).where(*_mine(user_id, plant_ids), Notification.read_at.is_(None))
    )
    return NotificationSummaryOut(unread=int(unread or 0), poll_seconds=_poll_seconds(session))


def mark_read(session: Session, user_id: int, notification_id: int) -> NotificationOut:
    notification = session.get(Notification, notification_id)
    if notification is None or notification.user_id != user_id:
        raise NotFoundError("El aviso no existe.")
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        session.commit()
    return NotificationOut.model_validate(notification)


def mark_all_read(session: Session, user_id: int) -> int:
    pending = list(
        session.scalars(
            select(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
    )
    now = datetime.now(UTC)
    for notification in pending:
        notification.read_at = now
    session.commit()
    return len(pending)
