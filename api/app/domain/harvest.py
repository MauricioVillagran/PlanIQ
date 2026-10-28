"""Plan de cosecha: cálculos, validaciones y diferencias entre versiones (sección 5.2, ADR 0005).

Funciones puras: reciben datos simples y no conocen la base de datos ni FastAPI.

- Biomasa estimada = peces × peso promedio (kg). Con peso de 3 decimales es exacta, sin redondeo.
- WFE proyectado = biomasa × factor de la planta (`harvest.wfe_factor`). El WFE de un grupo (día, turno,
  centro) se calcula sobre la biomasa del grupo y se redondea a 3 decimales una sola vez, así coincide
  con el cálculo manual "biomasa total × factor".
- Rango de peso plausible semiabierto [mínimo, máximo), como todos los rangos del sistema.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from app.domain.shifts import ShiftWindow

KG = Decimal("0.001")


@dataclass(frozen=True)
class HarvestLine:
    """Una línea del plan de cosecha, con los códigos para mostrar en mensajes y comparaciones."""

    key: int | str
    farm_center_id: int
    farm_center_code: str
    cage_id: int
    cage_code: str
    holding_cage_id: int
    holding_cage_code: str
    shift_id: int
    shift_name: str
    fish_count: int
    avg_weight_kg: Decimal
    order: int
    notes: str | None = None

    @property
    def biomass_kg(self) -> Decimal:
        return biomass_kg(self.fish_count, self.avg_weight_kg)


def biomass_kg(fish_count: int, avg_weight_kg: Decimal) -> Decimal:
    return (Decimal(fish_count) * avg_weight_kg).quantize(KG, rounding=ROUND_HALF_UP)


def wfe_kg(biomass: Decimal, factor: Decimal | None) -> Decimal | None:
    """WFE de una biomasa. Sin factor configurado no hay WFE (ADR 0005, decisión 1)."""
    if factor is None:
        return None
    return (biomass * factor).quantize(KG, rounding=ROUND_HALF_UP)


# --- Totales -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Totals:
    lines: int
    fish_count: int
    biomass_kg: Decimal
    wfe_kg: Decimal | None

    @property
    def avg_weight_kg(self) -> Decimal | None:
        """Peso promedio ponderado del grupo."""
        if self.fish_count == 0:
            return None
        return (self.biomass_kg / self.fish_count).quantize(KG, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class GroupTotals:
    id: int
    label: str
    totals: Totals


@dataclass(frozen=True)
class PlanSummary:
    day: Totals
    by_shift: list[GroupTotals]
    by_center: list[GroupTotals]


def totals(lines: Iterable[HarvestLine], wfe_factor: Decimal | None) -> Totals:
    items = list(lines)
    biomass = sum((line.biomass_kg for line in items), Decimal(0)).quantize(KG)
    return Totals(
        lines=len(items),
        fish_count=sum(line.fish_count for line in items),
        biomass_kg=biomass,
        wfe_kg=wfe_kg(biomass, wfe_factor),
    )


def summarize(
    lines: Sequence[HarvestLine],
    wfe_factor: Decimal | None,
    shift_order: Sequence[int] = (),
) -> PlanSummary:
    """Totales del día y su distribución por turno (en el orden de los turnos) y por centro."""
    by_shift: dict[int, list[HarvestLine]] = defaultdict(list)
    by_center: dict[int, list[HarvestLine]] = defaultdict(list)
    for line in lines:
        by_shift[line.shift_id].append(line)
        by_center[line.farm_center_id].append(line)

    position = {shift_id: i for i, shift_id in enumerate(shift_order)}
    shifts = sorted(by_shift, key=lambda s: (position.get(s, len(position)), s))
    return PlanSummary(
        day=totals(lines, wfe_factor),
        by_shift=[GroupTotals(s, by_shift[s][0].shift_name, totals(by_shift[s], wfe_factor)) for s in shifts],
        by_center=[
            GroupTotals(c, by_center[c][0].farm_center_code, totals(group, wfe_factor))
            for c, group in sorted(by_center.items(), key=lambda kv: kv[1][0].farm_center_code)
        ],
    )


# --- Validaciones --------------------------------------------------------------------------


class Severity(StrEnum):
    ERROR = "error"  # bloquea guardar y publicar
    WARNING = "warning"  # se muestra, no bloquea


@dataclass(frozen=True)
class Issue:
    code: str
    severity: Severity
    message: str
    line_keys: tuple[int | str, ...] = ()
    field: str | None = None


@dataclass(frozen=True)
class HoldingCageInfo:
    code: str
    capacity_fish: int


@dataclass(frozen=True)
class WeightRange:
    min_kg: Decimal
    max_kg: Decimal


def fmt_int(value: int) -> str:
    """Miles con punto, como en la interfaz: 12000 → "12.000"."""
    return f"{value:,}".replace(",", ".")


def fmt_kg(value: Decimal) -> str:
    """Decimales con coma y sin ceros de más: 4.500 → "4,5"."""
    text = format(value.normalize(), "f")
    return text.replace(".", ",")


def validate(
    lines: Sequence[HarvestLine],
    holding_cages: Mapping[int, HoldingCageInfo],
    weight_range: WeightRange | None,
    wfe_factor: Decimal | None,
) -> list[Issue]:
    """Reglas del plan de cosecha. Los errores bloquean; las advertencias se muestran."""
    issues: list[Issue] = []
    issues += _check_holding_capacity(lines, holding_cages)
    issues += _check_weight(lines, weight_range)
    issues += _check_repeated_cages(lines)
    if wfe_factor is None:
        issues.append(
            Issue(
                "wfe_factor_not_configured",
                Severity.WARNING,
                "WFE sin factor configurado: defina el parámetro harvest.wfe_factor de la planta.",
            )
        )
    return issues


def has_errors(issues: Iterable[Issue]) -> bool:
    return any(issue.severity is Severity.ERROR for issue in issues)


def _check_holding_capacity(
    lines: Sequence[HarvestLine], holding_cages: Mapping[int, HoldingCageInfo]
) -> list[Issue]:
    """Suma de peces por jaula de acopio y turno ≤ capacidad (ADR 0005, decisión 3)."""
    groups: dict[tuple[int, int], list[HarvestLine]] = defaultdict(list)
    for line in lines:
        groups[(line.holding_cage_id, line.shift_id)].append(line)
    issues = []
    for (holding_id, _shift_id), group in groups.items():
        info = holding_cages.get(holding_id)
        if info is None:
            continue
        fish = sum(line.fish_count for line in group)
        if fish > info.capacity_fish:
            issues.append(
                Issue(
                    "holding_cage_capacity_exceeded",
                    Severity.ERROR,
                    f"La jaula de acopio {info.code} recibe {fmt_int(fish)} peces en el turno "
                    f"{group[0].shift_name} y su capacidad es {fmt_int(info.capacity_fish)}.",
                    tuple(line.key for line in group),
                    "fish_count",
                )
            )
    return issues


def _check_weight(lines: Sequence[HarvestLine], weight_range: WeightRange | None) -> list[Issue]:
    if weight_range is None:
        return [
            Issue(
                "weight_range_not_configured",
                Severity.WARNING,
                "Rango de peso plausible no configurado: defina harvest.avg_weight_kg.min y "
                "harvest.avg_weight_kg.max de la planta.",
            )
        ]
    issues = []
    for line in lines:
        if not (weight_range.min_kg <= line.avg_weight_kg < weight_range.max_kg):
            issues.append(
                Issue(
                    "avg_weight_out_of_range",
                    Severity.ERROR,
                    f"Jaula {line.cage_code}: el peso promedio {fmt_kg(line.avg_weight_kg)} kg está fuera "
                    f"del rango plausible ({fmt_kg(weight_range.min_kg)} a menos de "
                    f"{fmt_kg(weight_range.max_kg)} kg).",
                    (line.key,),
                    "avg_weight_kg",
                )
            )
    return issues


def _check_repeated_cages(lines: Sequence[HarvestLine]) -> list[Issue]:
    """Una misma jaula dos veces en el día: advertencia, no bloquea (sección 5.2)."""
    by_cage: dict[int, list[HarvestLine]] = defaultdict(list)
    for line in lines:
        by_cage[line.cage_id].append(line)
    return [
        Issue(
            "cage_repeated",
            Severity.WARNING,
            f"La jaula {group[0].cage_code} del centro {group[0].farm_center_code} aparece "
            f"{len(group)} veces en el día.",
            tuple(line.key for line in group),
            "cage_id",
        )
        for group in by_cage.values()
        if len(group) > 1
    ]


# --- Diferencias entre versiones -----------------------------------------------------------

# Campos que se comparan y cómo se muestran (los ids se comparan por su código o nombre).
_COMPARED: dict[str, str] = {
    "farm_center_code": "Centro",
    "cage_code": "Jaula",
    "holding_cage_code": "Jaula de acopio",
    "shift_name": "Turno",
    "fish_count": "Peces",
    "avg_weight_kg": "Peso promedio (kg)",
    "order": "Orden de faena",
    "notes": "Observaciones",
}


@dataclass(frozen=True)
class FieldChange:
    field: str
    label: str
    old: Any
    new: Any


@dataclass(frozen=True)
class LineChange:
    key: int | str
    label: str
    changes: list[FieldChange]


@dataclass(frozen=True)
class PlanDiff:
    added: list[HarvestLine] = field(default_factory=list)
    removed: list[HarvestLine] = field(default_factory=list)
    changed: list[LineChange] = field(default_factory=list)
    totals_before: Totals | None = None
    totals_after: Totals | None = None

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed)


def _line_label(line: HarvestLine) -> str:
    return f"{line.farm_center_code} · jaula {line.cage_code} · turno {line.shift_name}"


def diff_versions(
    before: Sequence[HarvestLine], after: Sequence[HarvestLine], wfe_factor: Decimal | None = None
) -> PlanDiff:
    """Qué cambió entre dos versiones del plan, línea por línea y campo por campo.

    Las líneas se emparejan por su `key` (id de la línea), así un cambio de jaula o de turno aparece
    como modificación y no como baja más alta.
    """
    old = {line.key: line for line in before}
    new = {line.key: line for line in after}
    changed = []
    for key in sorted(old.keys() & new.keys(), key=lambda k: (new[k].order, str(k))):
        fields = [
            FieldChange(name, label, getattr(old[key], name), getattr(new[key], name))
            for name, label in _COMPARED.items()
            if getattr(old[key], name) != getattr(new[key], name)
        ]
        if fields:
            changed.append(LineChange(key, _line_label(new[key]), fields))
    return PlanDiff(
        added=sorted((new[k] for k in new.keys() - old.keys()), key=lambda line: line.order),
        removed=sorted((old[k] for k in old.keys() - new.keys()), key=lambda line: line.order),
        changed=changed,
        totals_before=totals(before, wfe_factor),
        totals_after=totals(after, wfe_factor),
    )


# --- Fecha productiva ----------------------------------------------------------------------


def productive_day_end(
    day: date, windows: Sequence[ShiftWindow], timezone: str | ZoneInfo
) -> datetime | None:
    """Instante (en UTC) en que termina la fecha productiva: el fin del turno que termina más tarde.

    Un turno nocturno de la fecha `day` termina al día siguiente. Sin turnos, no hay fin definido.
    Se usa para habilitar el cierre del plan (ADR 0005, decisión 8).

    Se devuelve en UTC a propósito: Python ignora el cambio de horario al restar o comparar dos
    datetimes con la misma zona, y el día del cambio la fecha productiva dura 23 o 25 horas.
    """
    if not windows:
        return None
    tz = timezone if isinstance(timezone, ZoneInfo) else ZoneInfo(timezone)
    ends = []
    for window in windows:
        end_day = day + timedelta(days=1) if window.crosses_midnight else day
        ends.append(datetime.combine(end_day, window.end, tzinfo=tz).astimezone(UTC))
    return max(ends)


def productive_day_start(
    day: date, windows: Sequence[ShiftWindow], timezone: str | ZoneInfo
) -> datetime | None:
    """Instante (en UTC) en que empieza la fecha productiva: el inicio del primer turno."""
    if not windows:
        return None
    tz = timezone if isinstance(timezone, ZoneInfo) else ZoneInfo(timezone)
    first: time = min(window.start for window in windows)
    return datetime.combine(day, first, tzinfo=tz).astimezone(UTC)
