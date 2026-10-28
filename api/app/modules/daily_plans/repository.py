"""Consultas del plan diario, incluidas las lecturas "tal como estaba" sobre las tablas temporales."""

from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.domain.harvest import HarvestLine
from app.modules.daily_plans.models import DailyPlan, DailyPlanVersion, HarvestEntry


def get_plan(session: Session, plan_id: int) -> DailyPlan | None:
    return session.get(DailyPlan, plan_id)


def find_plan(session: Session, plant_id: int, productive_date: date) -> DailyPlan | None:
    return session.scalars(
        select(DailyPlan).where(DailyPlan.plant_id == plant_id, DailyPlan.productive_date == productive_date)
    ).one_or_none()


def plans_between(session: Session, plant_id: int, date_from: date, date_to: date) -> list[DailyPlan]:
    return list(
        session.scalars(
            select(DailyPlan)
            .where(
                DailyPlan.plant_id == plant_id,
                DailyPlan.productive_date >= date_from,
                DailyPlan.productive_date <= date_to,
            )
            .order_by(DailyPlan.productive_date)
        )
    )


def versions(session: Session, plan_id: int) -> list[DailyPlanVersion]:
    return list(
        session.scalars(
            select(DailyPlanVersion)
            .where(DailyPlanVersion.daily_plan_id == plan_id)
            .order_by(DailyPlanVersion.number)
        )
    )


def get_version(session: Session, plan_id: int, number: int) -> DailyPlanVersion | None:
    return session.scalars(
        select(DailyPlanVersion).where(
            DailyPlanVersion.daily_plan_id == plan_id, DailyPlanVersion.number == number
        )
    ).one_or_none()


def to_line(entry: HarvestEntry) -> HarvestLine:
    """Línea vigente del ORM → línea del dominio."""
    return HarvestLine(
        key=entry.id,
        farm_center_id=entry.farm_center_id,
        farm_center_code=entry.farm_center.code,
        cage_id=entry.cage_id,
        cage_code=entry.cage.code,
        holding_cage_id=entry.holding_cage_id,
        holding_cage_code=entry.holding_cage.code,
        shift_id=entry.shift_id,
        shift_name=entry.shift.name,
        fish_count=entry.fish_count,
        avg_weight_kg=entry.avg_weight_kg,
        order=entry.sequence,
        notes=entry.notes,
    )


def to_lines(entries: Iterable[HarvestEntry]) -> list[HarvestLine]:
    return [to_line(entry) for entry in entries]


# Las líneas del plan en un instante pasado. Los maestros se leen con sus códigos actuales: los códigos
# son estables (ADR 0005, decisión 7) y así un cambio de nombre no aparece como diferencia del plan.
_ENTRIES_AS_OF = text(
    """
    SELECT e.id, e.farm_center_id, fc.code AS farm_center_code, e.cage_id, c.code AS cage_code,
           e.holding_cage_id, hc.code AS holding_cage_code, e.shift_id, s.name AS shift_name,
           e.fish_count, e.avg_weight_kg, e.sequence, e.notes
    FROM [plan].harvest_entries FOR SYSTEM_TIME AS OF :at AS e
    JOIN master.farm_centers AS fc ON fc.id = e.farm_center_id
    JOIN master.cages AS c ON c.id = e.cage_id
    JOIN master.holding_cages AS hc ON hc.id = e.holding_cage_id
    JOIN master.shifts AS s ON s.id = e.shift_id
    WHERE e.daily_plan_id = :plan_id
    ORDER BY e.sequence, e.id
    """
)


def entries_as_of(session: Session, plan_id: int, at: datetime) -> list[HarvestLine]:
    """El plan "tal como estaba" en el instante `at` (UTC), desde el historial temporal."""
    rows = session.execute(
        _ENTRIES_AS_OF, {"plan_id": plan_id, "at": at.astimezone(UTC).replace(tzinfo=None)}
    ).mappings()
    return [
        HarvestLine(
            key=row["id"],
            farm_center_id=row["farm_center_id"],
            farm_center_code=row["farm_center_code"],
            cage_id=row["cage_id"],
            cage_code=row["cage_code"],
            holding_cage_id=row["holding_cage_id"],
            holding_cage_code=row["holding_cage_code"],
            shift_id=row["shift_id"],
            shift_name=row["shift_name"],
            fish_count=row["fish_count"],
            avg_weight_kg=Decimal(row["avg_weight_kg"]),
            order=row["sequence"],
            notes=row["notes"],
        )
        for row in rows
    ]


def version_entries(session: Session, version: DailyPlanVersion) -> list[HarvestLine]:
    """Las líneas exactamente como quedaron en una versión publicada."""
    return entries_as_of(session, version.daily_plan_id, version.snapshot_at)
