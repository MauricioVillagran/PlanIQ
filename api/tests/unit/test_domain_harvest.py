"""Dominio del plan de cosecha, con un caso de control calculado a mano.

Caso de control (Planta Demo, factor WFE 0,92):

| Línea | Centro | Jaula | Acopio | Turno | Peces | Peso (kg) | Biomasa (kg)  |
|-------|--------|-------|--------|-------|-------|-----------|---------------|
| 1     | CD-01  | J-101 | A-1    | Día   | 5.000 | 4,500     | 22.500,000    |
| 2     | CD-01  | J-102 | A-1    | Día   | 6.000 | 4,250     | 25.500,000    |
| 3     | CD-02  | J-201 | A-2    | Noche | 8.000 | 3,875     | 31.000,000    |
| 4     | CD-02  | J-202 | A-2    | Noche | 3.500 | 5,125     | 17.937,500    |

Día: 22.500 peces · 96.937,500 kg · WFE 96.937,5 × 0,92 = 89.182,500 kg.
Turno Día: 11.000 peces · 48.000 kg · WFE 44.160. Turno Noche: 11.500 peces · 48.937,5 kg · WFE 45.022,5.
"""

from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest

from app.domain.harvest import (
    HarvestLine,
    HoldingCageInfo,
    Severity,
    WeightRange,
    biomass_kg,
    diff_versions,
    fmt_int,
    fmt_kg,
    has_errors,
    productive_day_end,
    productive_day_start,
    summarize,
    totals,
    validate,
    wfe_kg,
)
from app.domain.shifts import ShiftWindow

DIA, NOCHE = 1, 2
CD01, CD02 = 10, 20
A1, A2 = 100, 200
FACTOR = Decimal("0.92")
SANTIAGO = "America/Santiago"


def line(
    key: int, center: int, cage: str, holding: int, shift: int, fish: int, weight: str, order: int = 0
) -> HarvestLine:
    return HarvestLine(
        key=key,
        farm_center_id=center,
        farm_center_code="CD-01" if center == CD01 else "CD-02",
        cage_id=hash(cage) % 10_000,
        cage_code=cage,
        holding_cage_id=holding,
        holding_cage_code="A-1" if holding == A1 else "A-2",
        shift_id=shift,
        shift_name="Día" if shift == DIA else "Noche",
        fish_count=fish,
        avg_weight_kg=Decimal(weight),
        order=order or key,
    )


CONTROL = [
    line(1, CD01, "J-101", A1, DIA, 5000, "4.500"),
    line(2, CD01, "J-102", A1, DIA, 6000, "4.250"),
    line(3, CD02, "J-201", A2, NOCHE, 8000, "3.875"),
    line(4, CD02, "J-202", A2, NOCHE, 3500, "5.125"),
]
CAPACITY = {A1: HoldingCageInfo("A-1", 12_000), A2: HoldingCageInfo("A-2", 12_000)}
RANGE = WeightRange(Decimal("3.5"), Decimal("5.5"))


# --- Cálculos ------------------------------------------------------------------------------


def test_biomass_per_line_is_exact() -> None:
    assert [item.biomass_kg for item in CONTROL] == [
        Decimal("22500.000"),
        Decimal("25500.000"),
        Decimal("31000.000"),
        Decimal("17937.500"),
    ]
    assert biomass_kg(1, Decimal("4.125")) == Decimal("4.125")


def test_day_totals_match_the_manual_control() -> None:
    day = totals(CONTROL, FACTOR)
    assert day.lines == 4
    assert day.fish_count == 22_500
    assert day.biomass_kg == Decimal("96937.500")
    assert day.wfe_kg == Decimal("89182.500")
    assert day.avg_weight_kg == Decimal("4.308")  # 96.937,5 / 22.500 = 4,30833…


def test_summary_by_shift_and_center() -> None:
    summary = summarize(CONTROL, FACTOR, shift_order=[DIA, NOCHE])
    shifts = {g.label: g.totals for g in summary.by_shift}
    assert [g.label for g in summary.by_shift] == ["Día", "Noche"]
    assert (shifts["Día"].fish_count, shifts["Día"].biomass_kg, shifts["Día"].wfe_kg) == (
        11_000,
        Decimal("48000.000"),
        Decimal("44160.000"),
    )
    assert (shifts["Noche"].fish_count, shifts["Noche"].biomass_kg, shifts["Noche"].wfe_kg) == (
        11_500,
        Decimal("48937.500"),
        Decimal("45022.500"),
    )
    centers = {g.label: g.totals.biomass_kg for g in summary.by_center}
    assert centers == {"CD-01": Decimal("48000.000"), "CD-02": Decimal("48937.500")}
    # Los grupos suman el total del día.
    assert sum(g.totals.wfe_kg or 0 for g in summary.by_shift) == summary.day.wfe_kg


def test_shift_order_follows_the_plant_shifts() -> None:
    summary = summarize(CONTROL, FACTOR, shift_order=[NOCHE, DIA])
    assert [g.label for g in summary.by_shift] == ["Noche", "Día"]


def test_wfe_without_factor_is_empty() -> None:
    assert totals(CONTROL, None).wfe_kg is None
    assert totals(CONTROL, None).biomass_kg == Decimal("96937.500")


def test_wfe_rounds_half_up_to_grams() -> None:
    assert wfe_kg(Decimal("1000.001"), Decimal("0.9137")) == Decimal("913.701")  # 913,7009137
    assert wfe_kg(Decimal("0.005"), Decimal("0.1")) == Decimal("0.001")  # 0,0005 → 0,001


def test_empty_plan() -> None:
    day = totals([], FACTOR)
    assert (day.lines, day.fish_count, day.biomass_kg, day.wfe_kg, day.avg_weight_kg) == (
        0,
        0,
        Decimal("0.000"),
        Decimal("0.000"),
        None,
    )


# --- Validaciones --------------------------------------------------------------------------


def codes(issues: list) -> list[str]:  # type: ignore[type-arg]
    return [i.code for i in issues]


def test_valid_plan_has_no_issues() -> None:
    assert validate(CONTROL, CAPACITY, RANGE, FACTOR) == []


def test_holding_capacity_is_checked_per_shift() -> None:
    capacity = {A1: HoldingCageInfo("A-1", 12_000), A2: HoldingCageInfo("A-2", 11_000)}
    issues = validate(CONTROL, capacity, RANGE, FACTOR)
    assert codes(issues) == ["holding_cage_capacity_exceeded"]
    issue = issues[0]
    assert issue.severity is Severity.ERROR
    assert (
        issue.message
        == "La jaula de acopio A-2 recibe 11.500 peces en el turno Noche y su capacidad es 11.000."
    )
    assert issue.line_keys == (3, 4)
    assert issue.field == "fish_count"
    assert has_errors(issues)


def test_same_holding_cage_in_different_shifts_is_not_added_up() -> None:
    # A-1 recibe 11.000 en el turno Día y 7.000 en el turno Noche: 18.000 en el día,
    # pero nunca más de 12.000 a la vez.
    plan = [*CONTROL, line(5, CD01, "J-103", A1, NOCHE, 7000, "4.000")]
    capacity = {A1: HoldingCageInfo("A-1", 12_000), A2: HoldingCageInfo("A-2", 20_000)}
    assert validate(plan, capacity, RANGE, FACTOR) == []


def test_capacity_exactly_full_is_allowed() -> None:
    capacity = {A1: HoldingCageInfo("A-1", 11_000), A2: HoldingCageInfo("A-2", 11_500)}
    assert validate(CONTROL, capacity, RANGE, FACTOR) == []


@pytest.mark.parametrize(
    ("weight", "valid"),
    [("3.499", False), ("3.500", True), ("5.499", True), ("5.500", False), ("7.000", False)],
)
def test_weight_range_is_half_open(weight: str, valid: bool) -> None:
    issues = validate([line(1, CD01, "J-101", A1, DIA, 1000, weight)], CAPACITY, RANGE, FACTOR)
    assert ("avg_weight_out_of_range" not in codes(issues)) is valid


def test_weight_out_of_range_message() -> None:
    issues = validate([line(7, CD01, "J-104", A1, DIA, 1000, "6.250")], CAPACITY, RANGE, FACTOR)
    assert issues[0].message == (
        "Jaula J-104: el peso promedio 6,25 kg está fuera del rango plausible (3,5 a menos de 5,5 kg)."
    )
    assert issues[0].line_keys == (7,)
    assert issues[0].field == "avg_weight_kg"


def test_missing_configuration_only_warns() -> None:
    issues = validate(CONTROL, CAPACITY, None, None)
    assert codes(issues) == ["weight_range_not_configured", "wfe_factor_not_configured"]
    assert not has_errors(issues)


def test_repeated_cage_warns_without_blocking() -> None:
    plan = [*CONTROL, line(5, CD01, "J-101", A2, DIA, 500, "4.000")]
    issues = validate(
        plan, {A1: HoldingCageInfo("A-1", 20_000), A2: HoldingCageInfo("A-2", 20_000)}, RANGE, FACTOR
    )
    assert codes(issues) == ["cage_repeated"]
    assert issues[0].severity is Severity.WARNING
    assert issues[0].line_keys == (1, 5)
    assert issues[0].message == "La jaula J-101 del centro CD-01 aparece 2 veces en el día."
    assert not has_errors(issues)


def test_number_formatting_for_messages() -> None:
    assert fmt_int(1234567) == "1.234.567"
    assert fmt_kg(Decimal("4.500")) == "4,5"
    assert fmt_kg(Decimal("12.000")) == "12"


# --- Diferencias entre versiones -----------------------------------------------------------


def test_identical_versions_have_no_differences() -> None:
    diff = diff_versions(CONTROL, list(CONTROL), FACTOR)
    assert diff.is_empty


def test_diff_reports_field_level_changes_added_and_removed() -> None:
    after = [
        CONTROL[0],
        line(2, CD01, "J-103", A1, NOCHE, 6200, "4.250"),  # cambia jaula, turno y peces
        CONTROL[2],
        line(9, CD02, "J-203", A2, DIA, 1000, "4.000", order=5),  # nueva
    ]  # la línea 4 se elimina
    diff = diff_versions(CONTROL, after, FACTOR)

    assert [a.key for a in diff.added] == [9]
    assert [r.key for r in diff.removed] == [4]
    assert len(diff.changed) == 1
    change = diff.changed[0]
    assert change.key == 2
    assert change.label == "CD-01 · jaula J-103 · turno Noche"
    assert [(c.label, c.old, c.new) for c in change.changes] == [
        ("Jaula", "J-102", "J-103"),
        ("Turno", "Día", "Noche"),
        ("Peces", 6000, 6200),
    ]
    assert diff.totals_before is not None and diff.totals_after is not None
    assert diff.totals_before.fish_count == 22_500
    assert diff.totals_after.fish_count == 5000 + 6200 + 8000 + 1000


def test_reordering_is_a_change() -> None:
    reordered = [
        line(1, CD01, "J-101", A1, DIA, 5000, "4.500", order=2),
        line(2, CD01, "J-102", A1, DIA, 6000, "4.250", order=1),
    ]
    diff = diff_versions(CONTROL[:2], reordered)
    assert [(c.key, [f.field for f in c.changes]) for c in diff.changed] == [(2, ["order"]), (1, ["order"])]


# --- Fecha productiva ----------------------------------------------------------------------

DAY_SHIFT = ShiftWindow("Día", time(8, 0), time(20, 0))
NIGHT_SHIFT = ShiftWindow("Noche", time(20, 0), time(8, 0))


def test_productive_day_ends_with_the_night_shift_next_morning() -> None:
    end = productive_day_end(date(2026, 1, 12), [DAY_SHIFT, NIGHT_SHIFT], SANTIAGO)
    assert end is not None
    # Lunes 12-01-2026: el turno noche termina el martes 13 a las 08:00 (UTC-3) = 11:00 UTC.
    assert end == datetime(2026, 1, 13, 11, 0, tzinfo=UTC)
    assert end.tzinfo is UTC  # en UTC: restar o comparar instantes no sufre el cambio de horario


def test_productive_day_with_only_day_shift_ends_same_day() -> None:
    end = productive_day_end(date(2026, 7, 14), [DAY_SHIFT], SANTIAGO)
    assert end is not None and end.astimezone(UTC) == datetime(2026, 7, 15, 0, 0, tzinfo=UTC)  # 20:00 UTC-4


def test_productive_day_across_the_daylight_saving_change_lasts_25_hours() -> None:
    # Chile vuelve al horario de invierno el domingo 05-04-2026: la fecha productiva del sábado 4 dura 25 h.
    start = productive_day_start(date(2026, 4, 4), [DAY_SHIFT, NIGHT_SHIFT], SANTIAGO)
    end = productive_day_end(date(2026, 4, 4), [DAY_SHIFT, NIGHT_SHIFT], SANTIAGO)
    assert start is not None and end is not None
    assert (end - start).total_seconds() == 25 * 3600


def test_productive_day_without_shifts() -> None:
    assert productive_day_end(date(2026, 1, 12), [], SANTIAGO) is None
    assert productive_day_start(date(2026, 1, 12), [], SANTIAGO) is None
