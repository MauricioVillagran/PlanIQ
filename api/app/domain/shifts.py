"""Turnos y fecha productiva (sección 4 de la especificación).

Un turno se define por hora de inicio y de término en hora local de la planta. Si el término es
menor o igual que el inicio, el turno cruza la medianoche. La producción se imputa a la fecha
productiva del **inicio** del turno: a las 02:00 del martes, el turno noche que empezó el lunes
a las 22:00 imputa al lunes.

Los intervalos son semiabiertos [inicio, término): a la hora exacta de término ya rige el turno siguiente.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from itertools import combinations
from zoneinfo import ZoneInfo

MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True)
class ShiftWindow:
    name: str
    start: time
    end: time

    @property
    def crosses_midnight(self) -> bool:
        return self.end <= self.start

    @property
    def start_minute(self) -> int:
        return self.start.hour * 60 + self.start.minute

    @property
    def end_minute(self) -> int:
        return self.end.hour * 60 + self.end.minute

    @property
    def duration_minutes(self) -> int:
        return (self.end_minute - self.start_minute) % MINUTES_PER_DAY

    def segments(self) -> list[tuple[int, int]]:
        """Tramos [desde, hasta) en minutos dentro de un día. Un turno nocturno tiene dos tramos."""
        if not self.crosses_midnight:
            return [(self.start_minute, self.end_minute)]
        segments = [(self.start_minute, MINUTES_PER_DAY)]
        if self.end_minute > 0:
            segments.append((0, self.end_minute))
        return segments


def window_errors(window: ShiftWindow) -> list[str]:
    errors = []
    if window.start == window.end:
        errors.append("La hora de término debe ser distinta de la de inicio.")
    if window.start.second or window.end.second or window.start.microsecond or window.end.microsecond:
        errors.append("Las horas se definen en minutos (sin segundos).")
    return errors


def find_overlaps(windows: Sequence[ShiftWindow]) -> list[tuple[str, str]]:
    """Pares de turnos que se traslapan."""
    overlaps = []
    for a, b in combinations(windows, 2):
        if any(a1 < b2 and b1 < a2 for a1, a2 in a.segments() for b1, b2 in b.segments()):
            overlaps.append((a.name, b.name))
    return overlaps


def coverage_gaps(windows: Sequence[ShiftWindow]) -> list[tuple[time, time]]:
    """Tramos del día no cubiertos por ningún turno, como (desde, hasta) en hora local."""
    covered = sorted(seg for w in windows for seg in w.segments())
    gaps: list[tuple[int, int]] = []
    cursor = 0
    for start, end in covered:
        if start > cursor:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < MINUTES_PER_DAY:
        gaps.append((cursor, MINUTES_PER_DAY))
    # Un hueco que cruza la medianoche aparece partido en dos: se une.
    if len(gaps) >= 2 and gaps[0][0] == 0 and gaps[-1][1] == MINUTES_PER_DAY:
        gaps = [(gaps[-1][0], gaps[0][1]), *gaps[1:-1]]
    return [(_to_time(a), _to_time(b)) for a, b in gaps]


def _to_time(minute: int) -> time:
    minute %= MINUTES_PER_DAY
    return time(minute // 60, minute % 60)


def productive_date(
    moment: datetime, timezone: str | ZoneInfo, windows: Sequence[ShiftWindow]
) -> tuple[date, ShiftWindow | None]:
    """Fecha productiva y turno de un instante.

    `moment` debe tener zona (normalmente UTC, como se guarda). Si cae en un hueco entre turnos,
    se devuelve la fecha calendario local y ningún turno.
    """
    if moment.tzinfo is None:
        raise ValueError("productive_date requiere un datetime con zona horaria")
    tz = timezone if isinstance(timezone, ZoneInfo) else ZoneInfo(timezone)
    local = moment.astimezone(tz)
    minute = local.hour * 60 + local.minute
    for window in windows:
        for start, end in window.segments():
            if start <= minute < end:
                after_midnight = window.crosses_midnight and start == 0
                day = local.date() - timedelta(days=1) if after_midnight else local.date()
                return day, window
    return local.date(), None
