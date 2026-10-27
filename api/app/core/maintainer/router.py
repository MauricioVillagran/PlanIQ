"""Fábrica de routers de mantenedor: genera los mismos endpoints para cada recurso.

    GET    /<resource>                 listado paginado (q, status, sort, filtros)
    GET    /<resource>/export.xlsx     exportación a Excel con los mismos filtros
    GET    /<resource>/{id}            detalle
    POST   /<resource>                 alta
    PATCH  /<resource>/{id}            edición parcial con row_version (409 si cambió)
    POST   /<resource>/{id}/deactivate
    POST   /<resource>/{id}/activate
    GET    /<resource>/{id}/history    historial de auditoría

Los esquemas y permisos de cada recurso se inyectan en la firma de los endpoints antes de registrarlos
(`_annotate`): FastAPI los usa para validar y para el OpenAPI, y el código queda tipado para mypy.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, create_model

from app.core.config import get_settings
from app.core.errors import ErrorResponse
from app.core.maintainer.export import XLSX_MEDIA_TYPE, build_workbook
from app.core.maintainer.schemas import StrictInput, VersionedUpdate
from app.core.maintainer.service import ListQuery, MaintainerService, Status
from app.core.maintainer.spec import MaintainerSpec
from app.core.pagination import Page, PageParamsDep
from app.db.session import SessionDep
from app.modules.audit.schemas import AuditEntryOut
from app.modules.audit.service import record_history
from app.modules.auth.dependencies import CurrentUser, require_permission

ServiceFactory = Callable[..., MaintainerService]

QParam = Annotated[str | None, Query(max_length=100, description="Texto a buscar")]
StatusParam = Annotated[Status, Query(alias="status", description="active, inactive o all")]
SortParam = Annotated[str | None, Query(max_length=50, description="Campo de orden; '-' para descendente")]

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "No autenticado"},
    403: {"model": ErrorResponse, "description": "Sin permiso o sin acceso a la planta"},
    404: {"model": ErrorResponse, "description": "No existe o no es visible para el usuario"},
}
_WRITE_ERRORS: dict[int | str, dict[str, Any]] = {
    **_ERRORS,
    409: {
        "model": ErrorResponse,
        "description": "Modificado por otro usuario (details.current: datos vigentes)",
    },
    422: {"model": ErrorResponse, "description": "Validación o regla de negocio"},
}


def _annotate(func: Callable[..., Any], **annotations: Any) -> Callable[..., Any]:
    func.__annotations__ = {**func.__annotations__, **annotations}
    return func


def build_maintainer_router(
    spec: MaintainerSpec, service_cls: ServiceFactory = MaintainerService
) -> APIRouter:
    router = APIRouter(prefix=f"/{spec.resource}", tags=list(spec.tags or (spec.resource,)))
    out = spec.out_schema
    viewer = Annotated[CurrentUser, Depends(require_permission(spec.view_permission))]
    editor = Annotated[CurrentUser, Depends(require_permission(spec.edit_permission))]
    filters_model: type[BaseModel] = create_model(
        f"{out.__name__.removesuffix('Out')}Filters",
        **{name: (typ | None, None) for name, typ in spec.filters.items()},  # type: ignore[call-overload]
    )
    filters_dep = Annotated[filters_model, Depends()]

    def service(session: SessionDep, user: CurrentUser) -> MaintainerService:
        return service_cls(session, user, spec)

    def build_query(q: str | None, status_: Status, sort: str | None, filters: BaseModel) -> ListQuery:
        return ListQuery(q=q, status=status_, sort=sort, filters=filters.model_dump(exclude_none=True))

    def list_items(
        session: SessionDep,
        user: CurrentUser,
        params: PageParamsDep,
        filters: BaseModel,
        q: QParam = None,
        status_: StatusParam = "all",
        sort: SortParam = None,
    ) -> Any:
        rows, total = service(session, user).list(build_query(q, status_, sort, filters), params)
        return {
            "items": [out.model_validate(r) for r in rows],
            "page": params.page,
            "page_size": params.page_size,
            "total": total,
        }

    def export_items(
        session: SessionDep,
        user: CurrentUser,
        filters: BaseModel,
        q: QParam = None,
        status_: StatusParam = "all",
        sort: SortParam = None,
    ) -> Response:
        rows = service(session, user).export_rows(build_query(q, status_, sort, filters))
        content = build_workbook(
            rows, spec.export_columns, sheet_title=spec.resource, timezone=get_settings().app_timezone
        )
        filename = f"{spec.resource}-{datetime.now(UTC).strftime('%Y%m%d-%H%M')}.xlsx"
        return Response(
            content=content,
            media_type=XLSX_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def get_item(item_id: int, session: SessionDep, user: CurrentUser) -> Any:
        return service(session, user).get(item_id)

    def create_item(body: StrictInput, session: SessionDep, user: CurrentUser) -> Any:
        return service(session, user).create(body)

    def update_item(item_id: int, body: VersionedUpdate, session: SessionDep, user: CurrentUser) -> Any:
        return service(session, user).update(item_id, body)

    def deactivate_item(item_id: int, session: SessionDep, user: CurrentUser) -> Any:
        return service(session, user).set_active(item_id, active=False)

    def activate_item(item_id: int, session: SessionDep, user: CurrentUser) -> Any:
        return service(session, user).set_active(item_id, active=True)

    def item_history(
        item_id: int, session: SessionDep, user: CurrentUser, params: PageParamsDep
    ) -> Page[AuditEntryOut]:
        obj = service(session, user).get(item_id)
        return record_history(session, obj.__table__.fullname, item_id, params, user)

    label = spec.label
    search_help = f"Busca en: {', '.join(spec.search_fields)}. " if spec.search_fields else ""
    routes: list[tuple[str, str, Callable[..., Any], dict[str, Any]]] = [
        (
            "",
            "GET",
            _annotate(list_items, user=viewer, filters=filters_dep),
            {
                "response_model": Page[out],  # type: ignore[valid-type]
                "summary": f"Listado de {spec.resource}",
                "description": f"{search_help}Orden permitido: {', '.join(spec.sort_fields)}.",
                "responses": _ERRORS,
            },
        ),
        (
            "/export.xlsx",
            "GET",
            _annotate(export_items, user=viewer, filters=filters_dep),
            {
                "response_class": Response,
                "summary": f"Exportar {spec.resource} a Excel (mismos filtros del listado)",
                "responses": {
                    200: {"content": {XLSX_MEDIA_TYPE: {}}, "description": "Archivo .xlsx"},
                    **_ERRORS,
                },
            },
        ),
        (
            "/{item_id:int}",
            "GET",
            _annotate(get_item, user=viewer),
            {"response_model": out, "summary": f"Detalle de {label}", "responses": _ERRORS},
        ),
        (
            "",
            "POST",
            _annotate(create_item, user=editor, body=spec.create_schema),
            {
                "response_model": out,
                "status_code": status.HTTP_201_CREATED,
                "summary": f"Crear {label}",
                "responses": _WRITE_ERRORS,
            },
        ),
        (
            "/{item_id:int}",
            "PATCH",
            _annotate(update_item, user=editor, body=spec.update_schema),
            {"response_model": out, "summary": f"Editar {label}", "responses": _WRITE_ERRORS},
        ),
        (
            "/{item_id:int}/deactivate",
            "POST",
            _annotate(deactivate_item, user=editor),
            {"response_model": out, "summary": f"Desactivar {label}", "responses": _WRITE_ERRORS},
        ),
        (
            "/{item_id:int}/activate",
            "POST",
            _annotate(activate_item, user=editor),
            {"response_model": out, "summary": f"Activar {label}", "responses": _WRITE_ERRORS},
        ),
        (
            "/{item_id:int}/history",
            "GET",
            _annotate(item_history, user=viewer),
            {
                "response_model": Page[AuditEntryOut],
                "summary": f"Historial de cambios de {label}",
                "responses": _ERRORS,
            },
        ),
    ]
    for path, method, endpoint, options in routes:
        router.add_api_route(path, endpoint, methods=[method], **options)
    return router
