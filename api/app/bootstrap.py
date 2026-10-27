"""Primer arranque: crea el administrador inicial si la base no tiene usuarios.

Se ejecuta después de las migraciones (`python -m app.bootstrap`, servicio `migrate`). Es idempotente:
si ya existe algún usuario no hace nada. El administrador debe cambiar su contraseña al primer ingreso.
"""

import logging
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.db.session import get_sessionmaker
from app.modules.auth.security import hash_password
from app.modules.auth.service import count_users, normalize_username
from app.modules.roles.models import Role
from app.modules.users.models import User

logger = logging.getLogger("bootstrap")

ADMIN_ROLE_CODE = "admin"


def create_initial_admin(session: Session, settings: Settings) -> User | None:
    if count_users(session) > 0:
        logger.info("Ya existen usuarios: no se crea el administrador inicial")
        return None
    if not (
        settings.initial_admin_username and settings.initial_admin_email and settings.initial_admin_password
    ):
        logger.warning("Faltan INITIAL_ADMIN_USERNAME, INITIAL_ADMIN_EMAIL o INITIAL_ADMIN_PASSWORD")
        return None
    admin_role = session.scalar(select(Role).where(Role.code == ADMIN_ROLE_CODE))
    if admin_role is None:
        raise RuntimeError("No existe el rol admin: ¿se aplicaron las migraciones?")

    user = User(
        username=normalize_username(settings.initial_admin_username),
        email=settings.initial_admin_email.strip().lower(),
        full_name="Administrador",
        password_hash=hash_password(settings.initial_admin_password.get_secret_value()),
        must_change_password=True,
    )
    user.roles.append(admin_role)
    session.add(user)
    session.commit()
    logger.info("Administrador inicial creado", extra={"user_id": user.id, "username": user.username})
    return user


def main() -> int:
    settings = get_settings()
    setup_logging("bootstrap", settings.log_level)
    with get_sessionmaker()() as session:
        create_initial_admin(session, settings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
