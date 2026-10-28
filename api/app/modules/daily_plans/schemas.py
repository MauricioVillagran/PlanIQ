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
    closable_at: datetime | None = Field(
        description="Desde cuándo se puede cerrar: fin del último turno del día (null sin turnos)"
    )


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


# --- Flujo: publicar, cambios con motivo, cerrar y versiones (sección 6, ADR 0005) -----------

PlanRowVersion = Annotated[
    str, Field(pattern=ROW_VERSION_PATTERN, description="row_version del plan leído; si cambió, 409")
]
# Una línea nueva del lote se referencia como "new-<posición en add>" (por ejemplo en el orden).
EntryKey = int | Annotated[str, Field(pattern=r"^new-\d+$")]


class PlanTransitionIn(StrictInput):
    row_version: PlanRowVersion


class EntryRef(StrictInput):
    id: int = Field(ge=1)
    row_version: str = Field(pattern=ROW_VERSION_PATTERN)


class EntryChange(HarvestEntryUpdate):
    id: int = Field(ge=1)


class PlanChangesIn(StrictInput):
    """Lote de cambios sobre un plan publicado: produce una versión y un aviso (ADR 0005, decisión 2)."""

    row_version: PlanRowVersion
    reason: str = Field(min_length=5, max_length=500, examples=["Cambio de jaula por condición sanitaria"])
    add: list[HarvestEntryCreate] = Field(default_factory=list)
    update: list[EntryChange] = Field(default_factory=list)
    delete: list[EntryRef] = Field(default_factory=list)
    order: list[EntryKey] | None = Field(
        default=None, description="Orden de faena completo resultante (ids y new-<n>); sin él, se conserva"
    )


class VersionOut(BaseModel):
    number: int
    kind: str = Field(examples=["publish"], description="publish (versión 1) o change")
    reason: str | None
    created_at: datetime
    created_by: int | None
    created_by_name: str | None
    totals: TotalsOut


class PlanLineOut(BaseModel):
    """Una línea tal como estaba en una versión."""

    entry_id: int
    sequence: int
    farm_center_code: str
    cage_code: str
    holding_cage_code: str
    shift_name: str
    fish_count: int
    avg_weight_kg: DecimalStr
    biomass_kg: DecimalStr
    notes: str | None


class VersionDetailOut(BaseModel):
    version: VersionOut
    entries: list[PlanLineOut]


class FieldChangeOut(BaseModel):
    field: str
    label: str
    old: str | int | None
    new: str | int | None


class LineChangeOut(BaseModel):
    entry_id: int
    label: str
    changes: list[FieldChangeOut]


class VersionCompareOut(BaseModel):
    a: int
    b: int
    added: list[PlanLineOut]
    removed: list[PlanLineOut]
    changed: list[LineChangeOut]
    totals_a: TotalsOut
    totals_b: TotalsOut
