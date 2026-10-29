"""Avisos internos de la campana: cada usuario ve solo los suyos."""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.core.pagination import Page, PageParamsDep
from app.db.session import SessionDep
from app.modules.auth.dependencies import CurrentUserDep
from app.modules.notifications import service
from app.modules.notifications.schemas import NotificationOut, NotificationSummaryOut, ReadAllOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationOut], summary="Mis avisos, más recientes primero")
def list_notifications(
    session: SessionDep,
    user: CurrentUserDep,
    params: PageParamsDep,
    unread_only: Annotated[bool, Query(description="Solo los no leídos")] = False,
) -> Page[NotificationOut]:
    return service.list_notifications(session, user.id, user.plant_ids, params, unread_only)


@router.get(
    "/summary", response_model=NotificationSummaryOut, summary="Contador de no leídos para la campana"
)
def notifications_summary(session: SessionDep, user: CurrentUserDep) -> NotificationSummaryOut:
    return service.summary(session, user.id, user.plant_ids)


@router.post("/read-all", response_model=ReadAllOut, summary="Marcar todos mis avisos como leídos")
def read_all(session: SessionDep, user: CurrentUserDep) -> ReadAllOut:
    return ReadAllOut(updated=service.mark_all_read(session, user.id))


@router.post("/{notification_id}/read", response_model=NotificationOut, summary="Marcar un aviso como leído")
def read_one(
    session: SessionDep, user: CurrentUserDep, notification_id: Annotated[int, Path(ge=1)]
) -> NotificationOut:
    return service.mark_read(session, user.id, notification_id)
