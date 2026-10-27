"""Mantenedor de turnos por planta (sección 5.1).

Los turnos activos de una planta nunca se traslapan. La cobertura de 24 horas no se exige al editar
(se arma turno a turno), sino al usar los turnos: `GET /shifts/coverage` informa los huecos y si el
parámetro `shifts.full_coverage` la exige; la Fase 1 lo valida al crear el plan.
"""

from typing import Annotated, Any

from fastapi import Depends, Query
from sqlalchemy import select

from app.core.errors import BusinessRuleError, FieldError
from app.core.maintainer import ExportColumn, MaintainerService, MaintainerSpec, build_maintainer_router
from app.db.session import SessionDep
from app.domain.shifts import MINUTES_PER_DAY, coverage_gaps, find_overlaps, window_errors
from app.modules.auth.dependencies import CurrentUser, ensure_plant_access, require_permission
from app.modules.parameters.values import get_parameter
from app.modules.plants.models import Plant
from app.modules.shifts.models import Shift
from app.modules.shifts.schemas import CoverageGap, ShiftCoverageOut, ShiftCreate, ShiftOut, ShiftUpdate

FULL_COVERAGE_PARAMETER = "shifts.full_coverage"


def active_shifts(session: Any, plant_id: int, exclude_id: int | None = None) -> list[Shift]:
    query = select(Shift).where(Shift.plant_id == plant_id, Shift.is_active)
    if exclude_id is not None:
        query = query.where(Shift.id != exclude_id)
    return list(session.scalars(query.order_by(Shift.sort_order, Shift.start_time)))


class ShiftService(MaintainerService):
    def apply(self, obj: Any, values: dict[str, Any], *, creating: bool) -> None:
        super().apply(obj, values, creating=creating)
        if obj.start_time is not None and obj.end_time is not None:
            obj.crosses_midnight = obj.end_time <= obj.start_time

    def validate(self, obj: Any, *, creating: bool) -> None:
        if not self.session.scalar(select(Plant.id).where(Plant.id == obj.plant_id, Plant.is_active)):
            raise BusinessRuleError(
                "La planta no existe o está inactiva.",
                code="invalid_plant",
                field_errors=[FieldError(field="plant_id", message="Planta inválida.", code="invalid")],
            )
        errors = window_errors(obj.window())
        if errors:
            raise BusinessRuleError(
                "El horario del turno no es válido.",
                code="invalid_shift_window",
                field_errors=[FieldError(field="end_time", message=m, code="invalid") for m in errors],
            )
        duplicated = self.session.scalar(
            select(Shift.id).where(
                Shift.plant_id == obj.plant_id, Shift.name == obj.name, Shift.id != (obj.id or 0)
            )
        )
        if duplicated:
            raise BusinessRuleError(
                "Hay valores repetidos.",
                code="duplicate",
                field_errors=[
                    FieldError(
                        field="name", message="Ya existe un turno con ese nombre en la planta.", code="unique"
                    )
                ],
            )
        if obj.is_active is not False:
            self._check_overlaps(obj)

    def before_set_active(self, obj: Any, active: bool) -> None:
        if active:
            self._check_overlaps(obj)

    def _check_overlaps(self, obj: Shift) -> None:
        others = active_shifts(self.session, obj.plant_id, exclude_id=obj.id)
        overlaps = [
            b for a, b in find_overlaps([obj.window(), *(s.window() for s in others)]) if a == obj.name
        ]
        if overlaps:
            raise BusinessRuleError(
                f"El turno se traslapa con: {', '.join(overlaps)}.",
                code="shift_overlap",
                field_errors=[FieldError(field="start_time", message="Horario traslapado.", code="overlap")],
                details={"overlaps_with": overlaps},
            )


spec = MaintainerSpec(
    model=Shift,
    resource="shifts",
    label="turno",
    out_schema=ShiftOut,
    create_schema=ShiftCreate,
    update_schema=ShiftUpdate,
    view_permission="masters.view",
    edit_permission="masters.edit",
    search_fields=("name",),
    filters={"plant_id": int},
    sort_fields=("sort_order", "name", "start_time", "plant_id"),
    default_sort="sort_order",
    plant_field="plant_id",
    export_columns=(
        ExportColumn("Planta (id)", "plant_id", 12),
        ExportColumn("Turno", "name", 16),
        ExportColumn("Inicio", lambda s: s.start_time.strftime("%H:%M"), 10),
        ExportColumn("Término", lambda s: s.end_time.strftime("%H:%M"), 10),
        ExportColumn("Cruza medianoche", "crosses_midnight", 16),
        ExportColumn("Orden", "sort_order", 8),
        ExportColumn("Activo", "is_active", 8),
    ),
)

router = build_maintainer_router(spec, ShiftService)


@router.get("/coverage", response_model=ShiftCoverageOut, summary="Cobertura de las 24 horas de una planta")
def coverage(
    session: SessionDep,
    user: Annotated[CurrentUser, Depends(require_permission("masters.view"))],
    plant_id: Annotated[int, Query(ge=1)],
) -> ShiftCoverageOut:
    ensure_plant_access(user, plant_id)
    windows = [s.window() for s in active_shifts(session, plant_id)]
    gaps = coverage_gaps(windows)
    gap_minutes = sum(
        ((g_end.hour * 60 + g_end.minute) - (g_start.hour * 60 + g_start.minute)) % MINUTES_PER_DAY
        or MINUTES_PER_DAY
        for g_start, g_end in gaps
    )
    return ShiftCoverageOut(
        plant_id=plant_id,
        full_coverage_required=bool(get_parameter(session, FULL_COVERAGE_PARAMETER, plant_id)),
        covered=not gaps,
        gaps=[CoverageGap(start=a, end=b) for a, b in gaps],
        covered_minutes=MINUTES_PER_DAY - gap_minutes,
    )
