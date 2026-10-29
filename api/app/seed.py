"""Datos ficticios de desarrollo: `python -m app.seed` (solo con APP_ENV=development).

Crea una planta de demostración con turnos día y noche, centros, jaulas y acopios ficticios, parámetros y
planes de cosecha de ayer, hoy y mañana (inventados), y un
usuario por rol base con la contraseña de DEV_SEED_PASSWORD y sin cambio obligatorio.
Es idempotente: lo que ya existe no se toca.
Nunca usa datos reales de producción.
"""

import logging
import os
import sys
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import get_sessionmaker
from app.modules.audit.listener import register_audit_listeners, set_actor
from app.modules.auth.dependencies import build_current_user
from app.modules.auth.security import hash_password
from app.modules.daily_plans import repository
from app.modules.daily_plans.flow import PlanFlowService
from app.modules.daily_plans.models import DailyPlan
from app.modules.daily_plans.schemas import DailyPlanCreate, EntryChange, HarvestEntryCreate, PlanChangesIn
from app.modules.farms.models import Cage, FarmCenter, HoldingCage
from app.modules.parameters.models import Parameter
from app.modules.plants.models import Plant
from app.modules.roles.models import Role
from app.modules.shifts.models import Shift
from app.modules.users.models import User

logger = logging.getLogger("seed")

DEMO_PLANT = {"code": "DEMO", "name": "Planta Demo", "plant_type": "own", "location": "Ficticia"}
DEMO_SHIFTS = [("Día", time(8, 0), time(20, 0), 1), ("Noche", time(20, 0), time(8, 0), 2)]
# (código, nombre, zona, jaulas): nombres y capacidades ficticios.
DEMO_CENTERS = [
    ("CD-01", "Centro Demo Norte", "Barrio Demo 1", ["J-101", "J-102", "J-103", "J-104"]),
    ("CD-02", "Centro Demo Sur", "Barrio Demo 2", ["J-201", "J-202", "J-203"]),
]
DEMO_HOLDING_CAGES = [("A-1", 12_000), ("A-2", 12_000), ("A-3", 8_000)]
# (usuario, nombre, rol, con acceso a la planta demo)
DEMO_USERS = [
    ("demo.admin", "Admin Demo", "admin", False),
    ("demo.planificacion", "Planificación Demo", "planning", True),
    ("demo.produccion", "Producción Demo", "production", True),
    ("demo.calidad", "Calidad Demo", "quality", True),
]


def _seed_farms(session: Session, plant: Plant) -> None:
    for code, name, zone, cage_codes in DEMO_CENTERS:
        if session.scalar(select(FarmCenter.id).where(FarmCenter.code == code)):
            continue
        center = FarmCenter(code=code, name=name, zone=zone)
        session.add(center)
        session.flush()
        session.add_all(Cage(farm_center_id=center.id, code=c) for c in cage_codes)
        logger.info("Centro demo creado", extra={"code": code})
    for code, capacity in DEMO_HOLDING_CAGES:
        exists = session.scalar(
            select(HoldingCage.id).where(HoldingCage.plant_id == plant.id, HoldingCage.code == code)
        )
        if not exists:
            session.add(HoldingCage(plant_id=plant.id, code=code, capacity_fish=capacity))


# --- Plan de cosecha de demostración ------------------------------------------------------------
# Parámetros y cifras inventados, solo para ver la pantalla funcionando. Se arman con los mismos servicios
# de la API, así quedan versiones, historial temporal y avisos como en el uso real.

DEMO_PARAMETERS = [
    ("harvest.wfe_factor", "0.88", None, "Factor WFE de demostración (ficticio)"),
    ("harvest.avg_weight_kg.min", "2", "kg", "Peso promedio mínimo plausible de demostración (ficticio)"),
    ("harvest.avg_weight_kg.max", "9", "kg", "Peso promedio máximo plausible de demostración (ficticio)"),
]
# (centro, jaula, turno, acopio, peces, peso promedio kg)
DemoLine = tuple[str, str, str, str, int, str]
DEMO_YESTERDAY: list[DemoLine] = [
    ("CD-01", "J-104", "Día", "A-1", 8_000, "4.700"),
    ("CD-01", "J-101", "Día", "A-2", 3_000, "4.800"),
    ("CD-02", "J-203", "Noche", "A-2", 7_500, "4.950"),
]
DEMO_TODAY: list[DemoLine] = [
    ("CD-01", "J-101", "Día", "A-1", 6_800, "4.850"),
    ("CD-01", "J-102", "Día", "A-1", 5_000, "5.120"),
    ("CD-02", "J-201", "Día", "A-2", 9_500, "4.630"),
    ("CD-02", "J-202", "Noche", "A-1", 7_200, "5.010"),
    ("CD-01", "J-103", "Noche", "A-3", 6_000, "4.420"),
]
DEMO_TODAY_CHANGE_REASON = "Mortalidad en el traslado de J-102 y se suma J-203 al turno noche"


def _seed_parameters(session: Session, plant: Plant) -> None:
    for key, value, unit, description in DEMO_PARAMETERS:
        exists = session.scalar(
            select(Parameter.id).where(Parameter.key == key, Parameter.plant_id == plant.id)
        )
        if not exists:
            session.add(
                Parameter(
                    key=key,
                    plant_id=plant.id,
                    value_type="decimal",
                    value=value,
                    unit=unit,
                    description=description,
                )
            )
    session.commit()


def _entry(session: Session, plant: Plant, line: DemoLine) -> HarvestEntryCreate:
    center, cage, shift, holding, fish, weight = line
    cage_id = session.scalar(
        select(Cage.id)
        .join(FarmCenter, FarmCenter.id == Cage.farm_center_id)
        .where(FarmCenter.code == center, Cage.code == cage)
    )
    shift_id = session.scalar(select(Shift.id).where(Shift.plant_id == plant.id, Shift.name == shift))
    holding_id = session.scalar(
        select(HoldingCage.id).where(HoldingCage.plant_id == plant.id, HoldingCage.code == holding)
    )
    return HarvestEntryCreate(
        cage_id=cage_id or 0,
        holding_cage_id=holding_id or 0,
        shift_id=shift_id or 0,
        fish_count=fish,
        avg_weight_kg=Decimal(weight),
    )


def _publish_with_lines(flow: PlanFlowService, plant: Plant, day: date, lines: list[DemoLine]) -> DailyPlan:
    plan = flow.create(plant.id, day, DailyPlanCreate())
    for line in lines:
        flow.add_entry(plan.id, _entry(flow.session, plant, line))
    flow.session.refresh(plan)
    return flow.publish(plan.id, plan.row_version.hex())


def _seed_plans(session: Session, plant: Plant) -> None:
    planner = session.scalar(select(User).where(User.username == "demo.planificacion"))
    if planner is None:
        return
    set_actor(session, planner.id)
    flow = PlanFlowService(session, build_current_user(planner))
    today = datetime.now(ZoneInfo(plant.timezone)).date()
    existing = {
        p.productive_date
        for p in repository.plans_between(
            session, plant.id, today - timedelta(days=1), today + timedelta(days=1)
        )
    }

    if today - timedelta(days=1) not in existing:
        plan = _publish_with_lines(flow, plant, today - timedelta(days=1), DEMO_YESTERDAY)
        closable_at = flow.closable_at(plan)
        if closable_at is not None and datetime.now(UTC) >= closable_at:
            flow.close(plan.id, plan.row_version.hex())
        logger.info("Plan demo de ayer creado")

    if today not in existing:
        plan = _publish_with_lines(flow, plant, today, DEMO_TODAY)
        entries = {e.cage.code: e for e in plan.entries}
        j102 = entries["J-102"]
        flow.apply_changes(
            plan.id,
            PlanChangesIn(
                row_version=plan.row_version.hex(),
                reason=DEMO_TODAY_CHANGE_REASON,
                update=[EntryChange(id=j102.id, row_version=j102.row_version.hex(), fish_count=4_600)],
                add=[_entry(session, plant, ("CD-02", "J-203", "Noche", "A-1", 4_000, "4.900"))],
            ),
        )
        logger.info("Plan demo de hoy creado (versión 2)")

    if today + timedelta(days=1) not in existing:
        flow.create(plant.id, today + timedelta(days=1), DailyPlanCreate(copy_from=today))
        logger.info("Plan demo de mañana creado en Borrador")
    set_actor(session, None)


def seed(session: Session, password: str) -> None:
    plant = session.scalar(select(Plant).where(Plant.code == DEMO_PLANT["code"]))
    if plant is None:
        plant = Plant(**DEMO_PLANT)
        session.add(plant)
        session.flush()
        for name, start, end, order in DEMO_SHIFTS:
            session.add(
                Shift(
                    plant_id=plant.id,
                    name=name,
                    start_time=start,
                    end_time=end,
                    crosses_midnight=end <= start,
                    sort_order=order,
                )
            )
        logger.info("Planta demo creada", extra={"plant_id": plant.id})

    _seed_farms(session, plant)

    roles = {r.code: r for r in session.scalars(select(Role))}
    for username, full_name, role_code, with_plant in DEMO_USERS:
        if session.scalar(select(User.id).where(User.username == username)):
            continue
        user = User(
            username=username,
            email=f"{username}@example.com",
            full_name=full_name,
            password_hash=hash_password(password),
            must_change_password=False,
        )
        user.roles.append(roles[role_code])
        if with_plant:
            user.plants.append(plant)
        session.add(user)
        logger.info("Usuario demo creado", extra={"username": username})
    session.commit()

    _seed_parameters(session, plant)
    _seed_plans(session, plant)


def main() -> int:
    settings = get_settings()
    setup_logging("seed", settings.log_level)
    if settings.app_env != "development":
        logger.error("El seed de demostración solo corre con APP_ENV=development")
        return 1
    password = os.environ.get("DEV_SEED_PASSWORD", "")
    if len(password) < settings.auth_password_min_length:
        logger.error(
            "Defina DEV_SEED_PASSWORD en .env (al menos %s caracteres)", settings.auth_password_min_length
        )
        return 1
    register_audit_listeners()
    with get_sessionmaker()() as session:
        seed(session, password)
    return 0


if __name__ == "__main__":
    sys.exit(main())
