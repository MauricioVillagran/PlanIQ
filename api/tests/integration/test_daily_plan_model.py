"""Modelo del plan diario: restricciones y tablas temporales (historial "tal como estaba")."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import Connection, Engine, delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog
from app.modules.auth.dependencies import CurrentUser
from app.modules.daily_plans import repository
from app.modules.daily_plans.flow import PlanFlowService
from app.modules.daily_plans.models import DailyPlan, DailyPlanVersion, HarvestEntry, VersionKind
from app.modules.daily_plans.schemas import (
    DailyPlanCreate,
    EntryChange,
    EntryRef,
    HarvestEntryCreate,
    PlanChangesIn,
)
from app.modules.farms.models import Cage, FarmCenter, HoldingCage
from app.modules.plants.models import Plant
from app.modules.shifts.models import Shift

pytestmark = pytest.mark.integration


@dataclass
class Masters:
    plant: Plant
    center: FarmCenter
    cages: list[Cage]
    holding: HoldingCage
    day: Shift
    night: Shift


def _create_masters(session: Session, code: str) -> Masters:
    plant = Plant(code=code, name=f"Planta {code}", plant_type="own")
    center = FarmCenter(code=f"C{code}", name=f"Centro {code}")
    session.add_all([plant, center])
    session.flush()
    cages = [Cage(farm_center_id=center.id, code=f"J-{n}") for n in (1, 2, 3)]
    holding = HoldingCage(plant_id=plant.id, code="A-1", capacity_fish=50_000)
    day = Shift(plant_id=plant.id, name="Día", start_time=time(7), end_time=time(19), crosses_midnight=False)
    night = Shift(
        plant_id=plant.id, name="Noche", start_time=time(19), end_time=time(7), crosses_midnight=True
    )
    session.add_all([*cages, holding, day, night])
    session.flush()
    return Masters(plant, center, cages, holding, day, night)


def _entry(m: Masters, plan: DailyPlan, cage: Cage, fish: int, weight: str, seq: int) -> HarvestEntry:
    return HarvestEntry(
        plant_id=m.plant.id,
        daily_plan=plan,
        farm_center_id=m.center.id,
        cage_id=cage.id,
        holding_cage_id=m.holding.id,
        shift_id=m.day.id,
        fish_count=fish,
        avg_weight_kg=Decimal(weight),
        sequence=seq,
    )


def test_plan_tables_are_system_versioned_with_retention(connection: Connection) -> None:
    rows = connection.execute(
        text(
            """
            SELECT t.name, SCHEMA_NAME(h.schema_id) AS history_schema, h.name AS history_name,
                   t.history_retention_period, t.history_retention_period_unit_desc
            FROM sys.tables t JOIN sys.tables h ON h.object_id = t.history_table_id
            WHERE SCHEMA_NAME(t.schema_id) = 'plan' AND t.temporal_type = 2
            ORDER BY t.name
            """
        )
    ).all()
    assert [(r.name, r.history_schema, r.history_name) for r in rows] == [
        ("daily_plans", "plan_history", "daily_plans"),
        ("harvest_entries", "plan_history", "harvest_entries"),
    ]
    assert all(
        (r.history_retention_period, r.history_retention_period_unit_desc) == (5, "YEAR") for r in rows
    )


def test_one_plan_per_plant_and_productive_date(db_session: Session) -> None:
    m = _create_masters(db_session, "U1")
    db_session.add(DailyPlan(plant_id=m.plant.id, productive_date=date(2026, 11, 2)))
    db_session.flush()
    db_session.add(DailyPlan(plant_id=m.plant.id, productive_date=date(2026, 11, 2)))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_entry_rejects_non_positive_fish_count(db_session: Session) -> None:
    m = _create_masters(db_session, "U2")
    plan = DailyPlan(plant_id=m.plant.id, productive_date=date(2026, 11, 2))
    db_session.add(_entry(m, plan, m.cages[0], 0, "4.5", 1))
    with pytest.raises(IntegrityError):
        db_session.flush()


# --- Historial temporal --------------------------------------------------------------------
# El período de una fila es la hora de inicio de la transacción que la escribió. Las pruebas comunes
# corren dentro de una sola transacción que se revierte, así que esta usa transacciones reales y limpia
# lo que creó al terminar (el historial de plan_history queda: no tiene claves foráneas).


@pytest.fixture
def committed(engine: Engine) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        first_audit_id = session.scalar(select(func.max(AuditLog.id))) or 0
        try:
            yield session
        finally:
            session.rollback()
            plans = (
                select(DailyPlan.id).join(Plant, Plant.id == DailyPlan.plant_id).where(Plant.code == "TMP")
            )
            session.execute(delete(DailyPlanVersion).where(DailyPlanVersion.daily_plan_id.in_(plans)))
            session.execute(delete(HarvestEntry).where(HarvestEntry.daily_plan_id.in_(plans)))
            session.execute(delete(DailyPlan).where(DailyPlan.id.in_(plans)))
            plant_id = select(Plant.id).where(Plant.code == "TMP").scalar_subquery()
            center_id = select(FarmCenter.id).where(FarmCenter.code == "CTMP").scalar_subquery()
            session.execute(delete(Shift).where(Shift.plant_id == plant_id))
            session.execute(delete(HoldingCage).where(HoldingCage.plant_id == plant_id))
            session.execute(delete(Cage).where(Cage.farm_center_id == center_id))
            session.execute(delete(FarmCenter).where(FarmCenter.code == "CTMP"))
            session.execute(delete(Plant).where(Plant.code == "TMP"))
            session.execute(delete(AuditLog).where(AuditLog.id > first_audit_id))
            session.commit()


def _publish(
    session: Session, plan: DailyPlan, kind: VersionKind, reason: str | None = None
) -> DailyPlanVersion:
    """Lo que hará el servicio: subir la versión del plan y guardar su cabecera en la misma transacción."""
    plan.current_version += 1
    session.flush()
    version = DailyPlanVersion(
        plant_id=plan.plant_id, daily_plan_id=plan.id, number=plan.current_version, kind=kind, reason=reason
    )
    session.add(version)
    session.commit()
    return version


def test_history_rebuilds_each_version_as_it_was(committed: Session) -> None:
    session = committed
    m = _create_masters(session, "TMP")
    plan = DailyPlan(plant_id=m.plant.id, productive_date=date(2026, 11, 3))
    a = _entry(m, plan, m.cages[0], 10_000, "4.500", 1)
    b = _entry(m, plan, m.cages[1], 8_000, "5.200", 2)
    session.add_all([plan, a, b])
    session.commit()
    v1 = _publish(session, plan, VersionKind.PUBLISH)

    # Versión 2: cambia los peces de A, borra B y agrega C, todo en una transacción.
    a.fish_count = 12_000
    session.delete(b)
    c = _entry(m, plan, m.cages[2], 6_000, "3.900", 2)
    session.add(c)
    v2 = _publish(session, plan, VersionKind.CHANGE, "Cambio de jaula por condición sanitaria")

    # Cambio posterior sin versión (no debe aparecer en v2).
    a.notes = "Revisar"
    session.commit()

    lines_v1 = repository.version_entries(session, v1)
    assert [(line.cage_code, line.fish_count, line.avg_weight_kg) for line in lines_v1] == [
        ("J-1", 10_000, Decimal("4.500")),
        ("J-2", 8_000, Decimal("5.200")),
    ]
    lines_v2 = repository.version_entries(session, v2)
    assert [(line.cage_code, line.fish_count, line.notes) for line in lines_v2] == [
        ("J-1", 12_000, None),
        ("J-3", 6_000, None),
    ]
    current = repository.to_lines(
        session.scalars(
            select(HarvestEntry).where(HarvestEntry.daily_plan_id == plan.id).order_by(HarvestEntry.sequence)
        )
    )
    assert current[0].notes == "Revisar"


def test_flow_versions_and_compare_show_exactly_what_changed(committed: Session) -> None:
    session = committed
    m = _create_masters(session, "TMP")
    session.commit()
    user = CurrentUser(
        id=999_999,
        username="prueba",
        full_name="Prueba",
        email="prueba@example.com",
        must_change_password=False,
        role_codes=frozenset({"planning"}),
        permissions=frozenset({"plan.view", "plan.edit", "plan.publish", "plan.close"}),
        plant_ids=None,
    )
    flow = PlanFlowService(session, user)
    plan = flow.create(m.plant.id, date(2026, 11, 4), DailyPlanCreate())

    def line(cage: Cage, fish: int, weight: str) -> HarvestEntryCreate:
        return HarvestEntryCreate(
            cage_id=cage.id,
            holding_cage_id=m.holding.id,
            shift_id=m.day.id,
            fish_count=fish,
            avg_weight_kg=Decimal(weight),
        )

    a = flow.add_entry(plan.id, line(m.cages[0], 10_000, "4.5")).entry
    b = flow.add_entry(plan.id, line(m.cages[1], 8_000, "5.2")).entry
    assert a is not None and b is not None
    plan = flow.publish(plan.id, plan.row_version.hex())

    entries = {e.id: e for e in plan.entries}
    plan = flow.apply_changes(
        plan.id,
        PlanChangesIn(
            row_version=plan.row_version.hex(),
            reason="Jaula J-2 en ayuno extendido",
            update=[EntryChange(id=a.id, row_version=entries[a.id].row_version.hex(), fish_count=12_000)],
            delete=[EntryRef(id=b.id, row_version=entries[b.id].row_version.hex())],
            add=[line(m.cages[2], 6_000, "3.9")],
        ),
    )
    assert plan.current_version == 2

    versions = flow.versions(plan.id)
    assert [(v.number, v.kind, v.reason) for v in versions] == [
        (2, "change", "Jaula J-2 en ayuno extendido"),
        (1, "publish", None),
    ]
    assert versions[1].totals.fish_count == 18_000
    assert versions[0].totals.fish_count == 18_000  # 12.000 + 6.000

    diff = flow.compare(plan.id, 1, 2)
    assert [line.cage_code for line in diff.added] == ["J-3"]
    assert [line.cage_code for line in diff.removed] == ["J-2"]
    assert [(c.field, c.old, c.new) for c in diff.changed[0].changes] == [("fish_count", 10_000, 12_000)]
    assert flow.version_detail(plan.id, 1).entries[1].cage_code == "J-2"
