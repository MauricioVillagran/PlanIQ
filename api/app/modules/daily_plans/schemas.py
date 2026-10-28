from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.maintainer.schemas import ROW_VERSION_PATTERN, StrictInput
from app.core.types import DecimalStr

AvgWeight = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=3, examples=["4.850"])]


def _hex(value: object) -> object:
    return value.hex() if isinstance(value, bytes) else value


# --- Entrada -------------------------------------------------------------------------------


class DailyPlanCreate(StrictInput):
    copy_from: date | None = Field(
        default=None, description="Copiar las líneas del plan de esta fecha (normalmente el día anterior)"
    )


class HarvestEntryCreate(StrictInput):
    cage_id: int = Field(ge=1, description="La jaula define el centro")
    holding_cage_id: int = Field(ge=1)
    shift_id: int = Field(ge=1)
    fish_count: int = Field(gt=0, le=10_000_000, examples=[12000])
    avg_weight_kg: AvgWeight
    notes: str | None = Field(default=None, max_length=500)


class HarvestEntryUpdate(StrictInput):
    row_version: str = Field(pattern=ROW_VERSION_PATTERN)
    cage_id: int | None = Field(default=None, ge=1)
    holding_cage_id: int | None = Field(default=None, ge=1)
    shift_id: int | None = Field(default=None, ge=1)
    fish_count: int | None = Field(default=None, gt=0, le=10_000_000)
    avg_weight_kg: AvgWeight | None = None
    notes: str | None = Field(default=None, max_length=500)


class HarvestOrderIn(StrictInput):
    entry_ids: list[int] = Field(min_length=1, description="Todas las líneas del plan, en el orden de faena")


# --- Salida --------------------------------------------------------------------------------


class IssueOut(BaseModel):
    code: str = Field(examples=["cage_repeated"])
    severity: str = Field(examples=["warning"], description="error bloquea; warning solo avisa")
    message: str
    entry_ids: list[int] = Field(description="Líneas afectadas (vacío si es del plan completo)")
    field: str | None = None


class TotalsOut(BaseModel):
    lines: int
    fish_count: int
    biomass_kg: DecimalStr
    wfe_kg: DecimalStr | None = Field(description="Null si la planta no tiene factor WFE configurado")
    avg_weight_kg: DecimalStr | None


class GroupTotalsOut(BaseModel):
    id: int
    label: str
    totals: TotalsOut


class PlanSummaryOut(BaseModel):
    day: TotalsOut
    by_shift: list[GroupTotalsOut]
    by_center: list[GroupTotalsOut]
    issues: list[IssueOut]
    has_errors: bool
    wfe_factor: DecimalStr | None


class HarvestEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    row_version: str
    sequence: int = Field(description="Orden de faena")
    farm_center_id: int
    farm_center_code: str
    farm_center_name: str
    cage_id: int
    cage_code: str
    holding_cage_id: int
    holding_cage_code: str
    shift_id: int
    shift_name: str
    fish_count: int
    avg_weight_kg: DecimalStr
    biomass_kg: DecimalStr
    notes: str | None

    _row_version = field_validator("row_version", mode="before")(_hex)


class DailyPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plant_id: int
    productive_date: date
    status: str = Field(examples=["draft"], description="draft, published o closed")
    current_version: int = Field(description="0 mientras es Borrador")
    row_version: str
    published_at: datetime | None
    published_by: int | None
    closed_at: datetime | None
    closed_by: int | None
    created_at: datetime
    updated_at: datetime | None

    _row_version = field_validator("row_version", mode="before")(_hex)


class DailyPlanDetailOut(BaseModel):
    plan: DailyPlanOut
    entries: list[HarvestEntryOut]
    summary: PlanSummaryOut


class HarvestEntryResult(BaseModel):
    """Respuesta al guardar una línea: la línea, y el resumen con las advertencias aparte."""

    entry: HarvestEntryOut | None = Field(description="Null al eliminar")
    summary: PlanSummaryOut


class PlanDayOut(BaseModel):
    """Un día de la vista semanal. Sin plan (o Borrador sin permiso de edición): plan_id null."""

    productive_date: date
    plan_id: int | None
    status: str | None
    current_version: int | None
    totals: TotalsOut | None
    errors: int
    warnings: int
