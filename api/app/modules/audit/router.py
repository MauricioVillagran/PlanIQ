"""Consulta del registro de auditoría (permiso audit.view)."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response

from app.core.config import get_settings
from app.core.maintainer.export import XLSX_MEDIA_TYPE, build_workbook
from app.core.maintainer.spec import ExportColumn
from app.core.pagination import Page, PageParamsDep
from app.db.session import SessionDep
from app.modules.audit.labels import ACTION_LABELS, describe_changes, entity_label
from app.modules.audit.schemas import AuditEntityOption, AuditEntryOut, AuditUserOption
from app.modules.audit.service import (
    AuditFilters,
    distinct_entities,
    distinct_users,
    export_entries,
    list_entries,
)
from app.modules.auth.dependencies import CurrentUser, require_permission

router = APIRouter(prefix="/audit", tags=["audit"])

AuditViewer = Annotated[CurrentUser, Depends(require_permission("audit.view"))]

Action = Literal["create", "update", "deactivate", "activate", "delete"]


def _local_midnight_utc(day: date) -> datetime:
    tz = ZoneInfo(get_settings().app_timezone)
    return datetime.combine(day, time.min, tzinfo=tz).astimezone(UTC)


def audit_filters(
    entity: Annotated[str | None, Query(max_length=100, examples=["master.plants"])] = None,
    entity_id: Annotated[int | None, Query(ge=1)] = None,
    user_id: Annotated[int | None, Query(ge=1)] = None,
    action: Action | None = None,
    date_from: Annotated[
        date | None, Query(description="Desde este día (incluido), YYYY-MM-DD en la zona de la planta")
    ] = None,
    date_to: Annotated[
        date | None, Query(description="Hasta este día (incluido), YYYY-MM-DD en la zona de la planta")
    ] = None,
) -> AuditFilters:
    return AuditFilters(
        entity=entity,
        entity_id=entity_id,
        user_id=user_id,
        action=action,
        date_from=_local_midnight_utc(date_from) if date_from else None,
        date_to=_local_midnight_utc(date_to + timedelta(days=1)) if date_to else None,
    )


FiltersDep = Annotated[AuditFilters, Depends(audit_filters)]


@router.get("", response_model=Page[AuditEntryOut], summary="Registro de auditoría, más reciente primero")
def list_audit(
    session: SessionDep, viewer: AuditViewer, params: PageParamsDep, filters: FiltersDep
) -> Page[AuditEntryOut]:
    return list_entries(session, filters, params, viewer)


_EXPORT_COLUMNS = [
    ExportColumn("Fecha", lambda r: r[0].occurred_at, 20),
    ExportColumn("Usuario", lambda r: r[1] or "Sistema", 18),
    ExportColumn("Acción", lambda r: ACTION_LABELS.get(r[0].action, r[0].action), 15),
    ExportColumn("Tabla", lambda r: entity_label(r[0].entity), 20),
    ExportColumn("Registro", lambda r: r[0].entity_id, 10),
    ExportColumn("Planta", lambda r: r[0].plant_id, 10),
    ExportColumn("Cambios", lambda r: describe_changes(r[0].changes), 80),
    ExportColumn("Request ID", lambda r: r[0].request_id, 24),
]


@router.get(
    "/export.xlsx",
    response_class=Response,
    summary="Exportar la auditoría a Excel (mismos filtros del listado, máximo 50.000 filas)",
    responses={200: {"content": {XLSX_MEDIA_TYPE: {}}, "description": "Archivo .xlsx"}},
)
def export_audit(session: SessionDep, viewer: AuditViewer, filters: FiltersDep) -> Response:
    rows = export_entries(session, filters, viewer)
    settings = get_settings()
    content = build_workbook(rows, _EXPORT_COLUMNS, sheet_title="Auditoría", timezone=settings.app_timezone)
    stamp = datetime.now(ZoneInfo(settings.app_timezone)).strftime("%Y%m%d-%H%M")
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="auditoria-{stamp}.xlsx"'},
    )


@router.get("/entities", response_model=list[AuditEntityOption], summary="Tablas con registros de auditoría")
def list_audit_entities(session: SessionDep, viewer: AuditViewer) -> list[AuditEntityOption]:
    options = [AuditEntityOption(entity=e, label=entity_label(e)) for e in distinct_entities(session, viewer)]
    return sorted(options, key=lambda o: o.label)


@router.get("/users", response_model=list[AuditUserOption], summary="Usuarios con registros de auditoría")
def list_audit_users(session: SessionDep, viewer: AuditViewer) -> list[AuditUserOption]:
    return [
        AuditUserOption(id=uid, username=username, full_name=full_name)
        for uid, username, full_name in distinct_users(session, viewer)
    ]
