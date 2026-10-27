"""Datos ficticios de desarrollo: `python -m app.seed` (solo con APP_ENV=development).

Crea una planta de demostración con turnos día y noche y un usuario por rol base, todos con la
contraseña de DEV_SEED_PASSWORD y sin cambio obligatorio. Es idempotente: lo que ya existe no se toca.
Nunca usa datos reales de producción.
"""

import logging
import os
import sys
from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import get_sessionmaker
from app.modules.audit.listener import register_audit_listeners
from app.modules.auth.security import hash_password
from app.modules.plants.models import Plant
from app.modules.roles.models import Role
from app.modules.shifts.models import Shift
from app.modules.users.models import User

logger = logging.getLogger("seed")

DEMO_PLANT = {"code": "DEMO", "name": "Planta Demo", "plant_type": "own", "location": "Ficticia"}
DEMO_SHIFTS = [("Día", time(8, 0), time(20, 0), 1), ("Noche", time(20, 0), time(8, 0), 2)]
# (usuario, nombre, rol, con acceso a la planta demo)
DEMO_USERS = [
    ("demo.admin", "Admin Demo", "admin", False),
    ("demo.planificacion", "Planificación Demo", "planning", True),
    ("demo.produccion", "Producción Demo", "production", True),
    ("demo.calidad", "Calidad Demo", "quality", True),
]


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
