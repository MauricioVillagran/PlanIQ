"""Consulta del registro de auditoría (permiso audit.view)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime

from app.core.pagination import Page, PageParamsDep
from app.db.session import SessionDep
from app.modules.audit.schemas import AuditEntryOut
from app.modules.audit.service import AuditFilters, list_entries
from app.modules.auth.dependencies import CurrentUser, require_permission

router = APIRouter(prefix="/audit", tags=["audit"])

AuditViewer = Annotated[CurrentUser, Depends(require_permission("audit.view"))]


@router.get("", response_model=Page[AuditEntryOut], summary="Registro de auditoría, más reciente primero")
def list_audit(
    session: SessionDep,
    viewer: AuditViewer,
    params: PageParamsDep,
    entity: Annotated[str | None, Query(max_length=100, examples=["master.plants"])] = None,
    entity_id: Annotated[int | None, Query(ge=1)] = None,
    user_id: Annotated[int | None, Query(ge=1)] = None,
    action: Literal["create", "update", "deactivate", "activate", "delete"] | None = None,
    date_from: Annotated[
        AwareDatetime | None, Query(description="Desde (incluido), ISO 8601 con zona")
    ] = None,
    date_to: Annotated[AwareDatetime | None, Query(description="Hasta (excluido), ISO 8601 con zona")] = None,
) -> Page[AuditEntryOut]:
    filters = AuditFilters(
        entity=entity,
        entity_id=entity_id,
        user_id=user_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
    )
    return list_entries(session, filters, params, viewer)
