"""Casos de uso del plan diario de cosecha en Borrador (sección 5.2, ADR 0005).

Los cálculos y reglas están en app.domain.harvest; aquí se cargan los datos, se aplican los permisos y
la visibilidad, y se guardan los cambios. Un plan en Borrador solo lo ve quien puede editarlo; los
demás roles lo ven desde que se publica.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BusinessRuleError, ConflictError, FieldError, NotFoundError
from app.domain import harvest
from app.domain.harvest import HarvestLine, HoldingCageInfo, Issue, Severity, WeightRange
from app.domain.shifts import coverage_gaps
from app.modules.auth.dependencies import CurrentUser, ensure_plant_access
from app.modules.daily_plans import repository
from app.modules.daily_plans.models import DailyPlan, HarvestEntry, PlanStatus
from app.modules.daily_plans.schemas import (
    DailyPlanCreate,
    DailyPlanDetailOut,
    DailyPlanOut,
    GroupTotalsOut,
    HarvestEntryCreate,
    HarvestEntryOut,
    HarvestEntryResult,
    HarvestEntryUpdate,
    IssueOut,
    PlanDayOut,
    PlanSummaryOut,
    TotalsOut,
)
from app.modules.farms.models import Cage, HoldingCage
from app.modules.parameters.values import get_parameter
from app.modules.plants.models import Plant
from app.modules.shifts.models import Shift
from app.modules.shifts.router import FULL_COVERAGE_PARAMETER, active_shifts

WFE_FACTOR = "harvest.wfe_factor"
WEIGHT_MIN = "harvest.avg_weight_kg.min"
WEIGHT_MAX = "harvest.avg_weight_kg.max"
MAX_RANGE_DAYS = 31
NEW_KEY = "new"


# --- Reglas de la planta para una fecha ----------------------------------------------------


@dataclass(frozen=True)
class PlanRules:
    holding_cages: dict[int, HoldingCageInfo]
    weight_range: WeightRange | None
    wfe_factor: Decimal | None
    shift_order: list[int]


def _decimal_parameter(session: Session, key: str, plant_id: int, on: date) -> Decimal | None:
    value = get_parameter(session, key, plant_id, on)
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except ArithmeticError:
        return None


def load_rules(session: Session, plant_id: int, on: date) -> PlanRules:
    low = _decimal_parameter(session, WEIGHT_MIN, plant_id, on)
    high = _decimal_parameter(session, WEIGHT_MAX, plant_id, on)
    holding = list(session.scalars(select(HoldingCage).where(HoldingCage.plant_id == plant_id)))
    shifts = list(
        session.scalars(
            select(Shift).where(Shift.plant_id == plant_id).order_by(Shift.sort_order, Shift.start_time)
        )
    )
    return PlanRules(
        holding_cages={h.id: HoldingCageInfo(h.code, h.capacity_fish) for h in holding},
        weight_range=WeightRange(low, high) if low is not None and high is not None else None,
        wfe_factor=_decimal_parameter(session, WFE_FACTOR, plant_id, on),
        shift_order=[s.id for s in shifts],
    )


# --- Conversión a esquemas de salida -------------------------------------------------------


def totals_out(totals: harvest.Totals) -> TotalsOut:
    return TotalsOut(
        lines=totals.lines,
        fish_count=totals.fish_count,
        biomass_kg=totals.biomass_kg,
        wfe_kg=totals.wfe_kg,
        avg_weight_kg=totals.avg_weight_kg,
    )


def issue_out(issue: Issue) -> IssueOut:
    return IssueOut(
        code=issue.code,
        severity=issue.severity.value,
        message=issue.message,
        entry_ids=[key for key in issue.line_keys if isinstance(key, int)],
        field=issue.field,
    )


def summary_out(lines: list[HarvestLine], rules: PlanRules) -> PlanSummaryOut:
    summary = harvest.summarize(lines, rules.wfe_factor, rules.shift_order)
    issues = harvest.validate(lines, rules.holding_cages, rules.weight_range, rules.wfe_factor)
    return PlanSummaryOut(
        day=totals_out(summary.day),
        by_shift=[
            GroupTotalsOut(id=g.id, label=g.label, totals=totals_out(g.totals)) for g in summary.by_shift
        ],
        by_center=[
            GroupTotalsOut(id=g.id, label=g.label, totals=totals_out(g.totals)) for g in summary.by_center
        ],
        issues=[issue_out(i) for i in issues],
        has_errors=harvest.has_errors(issues),
        wfe_factor=rules.wfe_factor,
    )


# --- Servicio ------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Refs:
    cage: Cage
    holding_cage: HoldingCage
    shift: Shift


class DailyPlanService:
    def __init__(self, session: Session, user: CurrentUser) -> None:
        self.session = session
        self.user = user

    # Lectura ---------------------------------------------------------------------------

    def _visible(self, plan: DailyPlan) -> bool:
        return plan.status != PlanStatus.DRAFT or self.user.has_permission("plan.edit")

    def _plant(self, plant_id: int) -> Plant:
        ensure_plant_access(self.user, plant_id)
        plant = self.session.get(Plant, plant_id)
        if plant is None:
            raise NotFoundError("La planta no existe.")
        return plant

    def get(self, plan_id: int) -> DailyPlan:
        """Un plan fuera de las plantas del usuario, o un Borrador que no puede ver, responde 404."""
        plan = repository.get_plan(self.session, plan_id)
        if plan is None or not self.user.can_access_plant(plan.plant_id) or not self._visible(plan):
            raise NotFoundError("El plan no existe.", code="plan_not_found")
        return plan

    def get_by_date(self, plant_id: int, day: date) -> DailyPlan:
        self._plant(plant_id)
        plan = repository.find_plan(self.session, plant_id, day)
        if plan is None or not self._visible(plan):
            raise NotFoundError("No hay plan para esa fecha.", code="plan_not_found")
        return plan

    def rules(self, plan: DailyPlan) -> PlanRules:
        return load_rules(self.session, plan.plant_id, plan.productive_date)

    def summary(self, plan: DailyPlan) -> PlanSummaryOut:
        return summary_out(repository.to_lines(plan.entries), self.rules(plan))

    def closable_at(self, plan: DailyPlan) -> datetime | None:
        """Fin de la fecha productiva: fin del turno activo que termina más tarde (ADR 0005, decisión 8)."""
        plant = self.session.get(Plant, plan.plant_id)
        windows = [s.window() for s in active_shifts(self.session, plan.plant_id)]
        timezone = plant.timezone if plant is not None else get_settings().app_timezone
        return harvest.productive_day_end(plan.productive_date, windows, timezone)

    def detail(self, plan: DailyPlan) -> DailyPlanDetailOut:
        return DailyPlanDetailOut(
            plan=DailyPlanOut.model_validate(plan),
            entries=[HarvestEntryOut.model_validate(e) for e in plan.entries],
            summary=self.summary(plan),
            closable_at=self.closable_at(plan),
        )

    def week(self, plant_id: int, date_from: date, date_to: date) -> list[PlanDayOut]:
        self._plant(plant_id)
        if date_to < date_from:
            raise BusinessRuleError("La fecha final es anterior a la inicial.", code="invalid_range")
        if (date_to - date_from).days >= MAX_RANGE_DAYS:
            raise BusinessRuleError(
                f"El rango admite como máximo {MAX_RANGE_DAYS} días.", code="range_too_long"
            )
        plans = {
            p.productive_date: p for p in repository.plans_between(self.session, plant_id, date_from, date_to)
        }
        days = []
        for offset in range((date_to - date_from).days + 1):
            day = date_from + timedelta(days=offset)
            plan = plans.get(day)
            if plan is None or not self._visible(plan):
                days.append(
                    PlanDayOut(
                        productive_date=day,
                        plan_id=None,
                        status=None,
                        current_version=None,
                        totals=None,
                        errors=0,
                        warnings=0,
                    )
                )
                continue
            summary = self.summary(plan)
            days.append(
                PlanDayOut(
                    productive_date=day,
                    plan_id=plan.id,
                    status=plan.status,
                    current_version=plan.current_version,
                    totals=summary.day,
                    errors=sum(1 for i in summary.issues if i.severity == Severity.ERROR),
                    warnings=sum(1 for i in summary.issues if i.severity == Severity.WARNING),
                )
            )
        return days

    # Creación --------------------------------------------------------------------------

    def create(self, plant_id: int, day: date, data: DailyPlanCreate) -> DailyPlan:
        plant = self._plant(plant_id)
        if not plant.is_active:
            raise BusinessRuleError("La planta está inactiva.", code="plant_inactive")
        existing = repository.find_plan(self.session, plant_id, day)
        if existing is not None:
            raise ConflictError(
                "Ya existe un plan para esa fecha.", code="plan_exists", details={"plan_id": existing.id}
            )
        self._check_shift_coverage(plant_id, day)

        plan = DailyPlan(plant_id=plant_id, productive_date=day, status=PlanStatus.DRAFT)
        self.session.add(plan)
        if data.copy_from is not None:
            source = repository.find_plan(self.session, plant_id, data.copy_from)
            if source is None or not source.entries:
                raise BusinessRuleError(
                    "No hay un plan con líneas en la fecha a copiar.",
                    code="copy_source_not_found",
                    field_errors=[
                        FieldError(field="copy_from", message="Sin plan para copiar.", code="not_found")
                    ],
                )
            for entry in source.entries:
                plan.entries.append(
                    HarvestEntry(
                        plant_id=plant_id,
                        farm_center_id=entry.farm_center_id,
                        cage_id=entry.cage_id,
                        holding_cage_id=entry.holding_cage_id,
                        shift_id=entry.shift_id,
                        fish_count=entry.fish_count,
                        avg_weight_kg=entry.avg_weight_kg,
                        sequence=entry.sequence,
                        notes=entry.notes,
                    )
                )
        self.session.commit()
        return plan

    def _check_shift_coverage(self, plant_id: int, day: date) -> None:
        """Si la planta exige cobertura de 24 h y sus turnos tienen huecos, no se crea el plan (ADR 0005)."""
        if not get_parameter(self.session, FULL_COVERAGE_PARAMETER, plant_id, day):
            return
        gaps = coverage_gaps([s.window() for s in active_shifts(self.session, plant_id)])
        if gaps:
            ranges = ", ".join(f"{a.strftime('%H:%M')}–{b.strftime('%H:%M')}" for a, b in gaps)
            raise BusinessRuleError(
                f"La planta exige cobertura de 24 horas y sus turnos dejan huecos ({ranges}).",
                code="shift_coverage_incomplete",
            )

    # Líneas (solo en Borrador) -----------------------------------------------------------

    def _editable(self, plan_id: int) -> DailyPlan:
        plan = self.get(plan_id)
        if plan.status == PlanStatus.CLOSED:
            raise BusinessRuleError("El plan está cerrado y no se puede modificar.", code="plan_closed")
        if plan.status == PlanStatus.PUBLISHED:
            raise BusinessRuleError(
                "El plan está publicado: los cambios se envían juntos, con un motivo.", code="plan_published"
            )
        return plan

    def _entry(self, plan: DailyPlan, entry_id: int) -> HarvestEntry:
        entry = next((e for e in plan.entries if e.id == entry_id), None)
        if entry is None:
            raise NotFoundError("La línea no existe.", code="entry_not_found")
        return entry

    def _refs(self, plant_id: int, cage_id: int, holding_cage_id: int, shift_id: int) -> _Refs:
        errors = []
        cage = self.session.get(Cage, cage_id)
        if cage is None or not cage.is_active or not cage.farm_center.is_active:
            errors.append(
                FieldError(field="cage_id", message="Jaula inexistente o inactiva.", code="invalid")
            )
        holding = self.session.get(HoldingCage, holding_cage_id)
        if holding is None or holding.plant_id != plant_id or not holding.is_active:
            errors.append(
                FieldError(
                    field="holding_cage_id",
                    message="Jaula de acopio inválida para la planta.",
                    code="invalid",
                )
            )
        shift = self.session.get(Shift, shift_id)
        if shift is None or shift.plant_id != plant_id or not shift.is_active:
            errors.append(
                FieldError(field="shift_id", message="Turno inválido para la planta.", code="invalid")
            )
        if errors or cage is None or holding is None or shift is None:
            raise BusinessRuleError(
                "Revise los datos de la línea.", code="invalid_references", field_errors=errors
            )
        return _Refs(cage, holding, shift)

    def _check_line(self, plan: DailyPlan, candidate: HarvestLine, replaces: int | None) -> None:
        """Valida el plan con la línea nueva o modificada; solo bloquean los errores que la involucran."""
        lines = [line for line in repository.to_lines(plan.entries) if line.key != replaces]
        lines.append(candidate)
        rules = self.rules(plan)
        issues = harvest.validate(lines, rules.holding_cages, rules.weight_range, rules.wfe_factor)
        blocking = [i for i in issues if i.severity is Severity.ERROR and candidate.key in i.line_keys]
        if blocking:
            raise BusinessRuleError(
                blocking[0].message,
                code="harvest_entry_invalid",
                field_errors=[
                    FieldError(field=i.field or "fish_count", message=i.message, code=i.code)
                    for i in blocking
                ],
                details={"issues": [issue_out(i).model_dump() for i in blocking]},
            )

    @staticmethod
    def _candidate(key: int | str, refs: _Refs, values: dict[str, Any], sequence: int) -> HarvestLine:
        return HarvestLine(
            key=key,
            farm_center_id=refs.cage.farm_center_id,
            farm_center_code=refs.cage.farm_center.code,
            cage_id=refs.cage.id,
            cage_code=refs.cage.code,
            holding_cage_id=refs.holding_cage.id,
            holding_cage_code=refs.holding_cage.code,
            shift_id=refs.shift.id,
            shift_name=refs.shift.name,
            fish_count=values["fish_count"],
            avg_weight_kg=values["avg_weight_kg"],
            order=sequence,
            notes=values.get("notes"),
        )

    def _result(self, plan: DailyPlan, entry: HarvestEntry | None) -> HarvestEntryResult:
        self.session.refresh(plan)
        return HarvestEntryResult(
            entry=HarvestEntryOut.model_validate(entry) if entry is not None else None,
            summary=self.summary(plan),
        )

    def add_entry(self, plan_id: int, data: HarvestEntryCreate) -> HarvestEntryResult:
        plan = self._editable(plan_id)
        refs = self._refs(plan.plant_id, data.cage_id, data.holding_cage_id, data.shift_id)
        sequence = max((e.sequence for e in plan.entries), default=0) + 1
        values = data.model_dump()
        self._check_line(plan, self._candidate(NEW_KEY, refs, values, sequence), replaces=None)

        entry = HarvestEntry(
            plant_id=plan.plant_id,
            farm_center_id=refs.cage.farm_center_id,
            sequence=sequence,
            **values,
        )
        plan.entries.append(entry)
        self.session.commit()
        return self._result(plan, entry)

    def update_entry(self, plan_id: int, entry_id: int, data: HarvestEntryUpdate) -> HarvestEntryResult:
        plan = self._editable(plan_id)
        entry = self._entry(plan, entry_id)
        if entry.row_version.hex() != data.row_version:
            raise ConflictError(
                details={"current": HarvestEntryOut.model_validate(entry).model_dump(mode="json")}
            )
        changes = data.model_dump(exclude_unset=True, exclude={"row_version"})
        values = {
            "fish_count": entry.fish_count,
            "avg_weight_kg": entry.avg_weight_kg,
            "notes": entry.notes,
            "cage_id": entry.cage_id,
            "holding_cage_id": entry.holding_cage_id,
            "shift_id": entry.shift_id,
            **{k: v for k, v in changes.items() if v is not None or k == "notes"},
        }
        refs = self._refs(plan.plant_id, values["cage_id"], values["holding_cage_id"], values["shift_id"])
        self._check_line(plan, self._candidate(entry.id, refs, values, entry.sequence), replaces=entry.id)

        for key, value in values.items():
            setattr(entry, key, value)
        entry.farm_center_id = refs.cage.farm_center_id
        self.session.commit()
        return self._result(plan, entry)

    def delete_entry(self, plan_id: int, entry_id: int, row_version: str) -> HarvestEntryResult:
        plan = self._editable(plan_id)
        entry = self._entry(plan, entry_id)
        if entry.row_version.hex() != row_version:
            raise ConflictError(
                details={"current": HarvestEntryOut.model_validate(entry).model_dump(mode="json")}
            )
        plan.entries.remove(entry)
        for position, other in enumerate(sorted(plan.entries, key=lambda e: e.sequence), start=1):
            if other.sequence != position:
                other.sequence = position
        self.session.commit()
        return self._result(plan, None)

    def reorder(self, plan_id: int, entry_ids: list[int]) -> DailyPlanDetailOut:
        plan = self._editable(plan_id)
        current = {e.id: e for e in plan.entries}
        if sorted(entry_ids) != sorted(current):
            raise BusinessRuleError(
                "El orden debe incluir todas las líneas del plan, una vez cada una.", code="invalid_order"
            )
        for position, entry_id in enumerate(entry_ids, start=1):
            if current[entry_id].sequence != position:
                current[entry_id].sequence = position
        self.session.commit()
        self.session.refresh(plan)
        return self.detail(plan)
