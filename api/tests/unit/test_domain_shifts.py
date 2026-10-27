from datetime import UTC, date, datetime, time

import pytest

from app.domain.shifts import ShiftWindow, coverage_gaps, find_overlaps, productive_date, window_errors

DAY = ShiftWindow("Día", time(8, 0), time(20, 0))
NIGHT = ShiftWindow("Noche", time(20, 0), time(8, 0))
SANTIAGO = "America/Santiago"


def test_night_shift_crosses_midnight() -> None:
    assert NIGHT.crosses_midnight is True
    assert DAY.crosses_midnight is False
    assert NIGHT.duration_minutes == 12 * 60
    assert NIGHT.segments() == [(20 * 60, 1440), (0, 8 * 60)]


def test_shift_ending_exactly_at_midnight_has_one_segment() -> None:
    late = ShiftWindow("Tarde", time(16, 0), time(0, 0))
    assert late.crosses_midnight is True
    assert late.segments() == [(16 * 60, 1440)]


@pytest.mark.parametrize(
    ("window", "expected"),
    [
        (ShiftWindow("X", time(8, 0), time(8, 0)), ["La hora de término debe ser distinta de la de inicio."]),
        (ShiftWindow("X", time(8, 0, 30), time(9, 0)), ["Las horas se definen en minutos (sin segundos)."]),
        (DAY, []),
    ],
)
def test_window_errors(window: ShiftWindow, expected: list[str]) -> None:
    assert window_errors(window) == expected


def test_day_and_night_do_not_overlap_and_cover_the_day() -> None:
    assert find_overlaps([DAY, NIGHT]) == []
    assert coverage_gaps([DAY, NIGHT]) == []


def test_overlap_detected_across_midnight() -> None:
    early = ShiftWindow("Madrugada", time(6, 0), time(10, 0))
    assert find_overlaps([NIGHT, early]) == [("Noche", "Madrugada")]
    assert find_overlaps([DAY, early]) == [("Día", "Madrugada")]


def test_touching_shifts_do_not_overlap() -> None:
    a = ShiftWindow("A", time(6, 0), time(14, 0))
    b = ShiftWindow("B", time(14, 0), time(22, 0))
    assert find_overlaps([a, b]) == []


def test_coverage_gap_across_midnight_is_merged() -> None:
    a = ShiftWindow("A", time(6, 0), time(14, 0))
    b = ShiftWindow("B", time(14, 0), time(22, 0))
    assert coverage_gaps([a, b]) == [(time(22, 0), time(6, 0))]


def test_coverage_gaps_inside_the_day() -> None:
    a = ShiftWindow("A", time(0, 0), time(8, 0))
    b = ShiftWindow("B", time(9, 0), time(0, 0))
    assert coverage_gaps([a, b]) == [(time(8, 0), time(9, 0))]
    assert coverage_gaps([]) == [(time(0, 0), time(0, 0))]


# --- Fecha productiva (Chile continental: UTC-3 en verano, UTC-4 en invierno) ---------------


@pytest.mark.parametrize(
    ("utc_moment", "expected_date", "expected_shift"),
    [
        # Martes 13-01-2026 02:00 en Santiago (UTC-3) → turno noche que empezó el lunes 12.
        (datetime(2026, 1, 13, 5, 0, tzinfo=UTC), date(2026, 1, 12), "Noche"),
        # Lunes 12-01-2026 22:00 en Santiago → turno noche del mismo lunes.
        (datetime(2026, 1, 13, 1, 0, tzinfo=UTC), date(2026, 1, 12), "Noche"),
        # Martes 13-01-2026 10:00 en Santiago → turno día del martes.
        (datetime(2026, 1, 13, 13, 0, tzinfo=UTC), date(2026, 1, 13), "Día"),
        # Límite: 08:00 exactas ya es turno día (intervalos semiabiertos).
        (datetime(2026, 1, 13, 11, 0, tzinfo=UTC), date(2026, 1, 13), "Día"),
        # Límite: 07:59 sigue siendo el turno noche del día anterior.
        (datetime(2026, 1, 13, 10, 59, tzinfo=UTC), date(2026, 1, 12), "Noche"),
        # Invierno (UTC-4): miércoles 15-07-2026 03:00 local → noche del martes 14.
        (datetime(2026, 7, 15, 7, 0, tzinfo=UTC), date(2026, 7, 14), "Noche"),
    ],
)
def test_productive_date_with_night_shift(
    utc_moment: datetime, expected_date: date, expected_shift: str
) -> None:
    day, shift = productive_date(utc_moment, SANTIAGO, [DAY, NIGHT])
    assert day == expected_date
    assert shift is not None and shift.name == expected_shift


def test_productive_date_in_a_gap_returns_calendar_date() -> None:
    a = ShiftWindow("A", time(8, 0), time(16, 0))
    # 18:00 local del 13-01-2026: fuera de turno.
    day, shift = productive_date(datetime(2026, 1, 13, 21, 0, tzinfo=UTC), SANTIAGO, [a])
    assert (day, shift) == (date(2026, 1, 13), None)


def test_productive_date_requires_timezone() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        productive_date(datetime(2026, 1, 13, 5, 0), SANTIAGO, [DAY])
