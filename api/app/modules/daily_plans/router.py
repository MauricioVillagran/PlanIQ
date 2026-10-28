"""Plan diario de cosecha (sección 5.2). Rutas por planta y fecha, y por id de plan (ADR 0001, decisión 6)."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, status

from app.db.session import SessionDep
from app.modules.auth.dependencies import CurrentUser, require_permission
from app.modules.daily_plans.schemas import (
    DailyPlanCreate,
    DailyPlanDetailOut,
    HarvestEntryCreate,
    HarvestEntryResult,
    HarvestEntryUpdate,
    HarvestOrderIn,
    PlanDayOut,
    PlanSummaryOut,
)
from app.modules.daily_plans.service import DailyPlanService

router = APIRouter(tags=["daily-plans"])

Viewer = Annotated[CurrentUser, Depends(require_permission("plan.view"))]
Editor = Annotated[CurrentUser, Depends(require_permission("plan.edit"))]
PlantId = Annotated[int, Path(ge=1)]
PlanId = Annotated[int, Path(ge=1)]
ProductiveDate = Annotated[date, Path(description="Fecha productiva YYYY-MM-DD", examples=["2026-10-28"])]
RowVersion = Annotated[str, Query(pattern=r"^[0-9a-f]{16}$", description="row_version leído de la línea")]

_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"description": "Sin plan, o Borrador sin permiso de edición"}
}


@router.get(
    "/plants/{plant_id}/daily-plans",
    response_model=list[PlanDayOut],
    summary="Vista semanal: estado y totales por día (máximo 31 días)",
)
def list_plans(
    session: SessionDep,
    user: Viewer,
    plant_id: PlantId,
    date_from: Annotated[date, Query(alias="from", examples=["2026-10-27"])],
    date_to: Annotated[date, Query(alias="to", examples=["2026-11-02"])],
) -> list[PlanDayOut]:
    return DailyPlanService(session, user).week(plant_id, date_from, date_to)


@router.get(
    "/plants/{plant_id}/daily-plans/{productive_date}",
    response_model=DailyPlanDetailOut,
    summary="Plan de una planta y fecha productiva, con líneas, totales y validaciones",
    responses=_NOT_FOUND,
)
def get_plan_by_date(
    session: SessionDep, user: Viewer, plant_id: PlantId, productive_date: ProductiveDate
) -> DailyPlanDetailOut:
    service = DailyPlanService(session, user)
    return service.detail(service.get_by_date(plant_id, productive_date))


@router.post(
    "/plants/{plant_id}/daily-plans/{productive_date}",
    response_model=DailyPlanDetailOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear el plan en Borrador, vacío o copiando las líneas de otra fecha",
    responses={409: {"description": "Ya existe un plan para esa fecha"}},
)
def create_plan(
    session: SessionDep,
    user: Editor,
    plant_id: PlantId,
    productive_date: ProductiveDate,
    body: DailyPlanCreate,
) -> DailyPlanDetailOut:
    service = DailyPlanService(session, user)
    return service.detail(service.create(plant_id, productive_date, body))


@router.get(
    "/daily-plans/{plan_id}", response_model=DailyPlanDetailOut, summary="Plan por id", responses=_NOT_FOUND
)
def get_plan(session: SessionDep, user: Viewer, plan_id: PlanId) -> DailyPlanDetailOut:
    service = DailyPlanService(session, user)
    return service.detail(service.get(plan_id))


@router.get(
    "/daily-plans/{plan_id}/summary",
    response_model=PlanSummaryOut,
    summary="Totales del día, por turno y por centro, con errores y advertencias",
)
def get_summary(session: SessionDep, user: Viewer, plan_id: PlanId) -> PlanSummaryOut:
    service = DailyPlanService(session, user)
    return service.summary(service.get(plan_id))


@router.post(
    "/daily-plans/{plan_id}/harvest-entries",
    response_model=HarvestEntryResult,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar una línea al plan en Borrador (al final del orden de faena)",
)
def add_entry(
    session: SessionDep, user: Editor, plan_id: PlanId, body: HarvestEntryCreate
) -> HarvestEntryResult:
    return DailyPlanService(session, user).add_entry(plan_id, body)


@router.put(
    "/daily-plans/{plan_id}/harvest-entries/order",
    response_model=DailyPlanDetailOut,
    summary="Reordenar la orden de faena (todas las líneas, en el orden nuevo)",
)
def reorder_entries(
    session: SessionDep, user: Editor, plan_id: PlanId, body: HarvestOrderIn
) -> DailyPlanDetailOut:
    return DailyPlanService(session, user).reorder(plan_id, body.entry_ids)


@router.patch(
    "/daily-plans/{plan_id}/harvest-entries/{entry_id}",
    response_model=HarvestEntryResult,
    summary="Modificar una línea del plan en Borrador",
    responses={
        409: {"description": "Otro usuario modificó la línea; details.current trae los datos vigentes"}
    },
)
def update_entry(
    session: SessionDep,
    user: Editor,
    plan_id: PlanId,
    entry_id: Annotated[int, Path(ge=1)],
    body: HarvestEntryUpdate,
) -> HarvestEntryResult:
    return DailyPlanService(session, user).update_entry(plan_id, entry_id, body)


@router.delete(
    "/daily-plans/{plan_id}/harvest-entries/{entry_id}",
    response_model=HarvestEntryResult,
    summary="Eliminar una línea del plan en Borrador",
)
def delete_entry(
    session: SessionDep,
    user: Editor,
    plan_id: PlanId,
    entry_id: Annotated[int, Path(ge=1)],
    row_version: RowVersion,
) -> HarvestEntryResult:
    return DailyPlanService(session, user).delete_entry(plan_id, entry_id, row_version)
