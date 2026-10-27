"""Fixtures comunes.

Las pruebas de integración usan la base `<DB_NAME>_test` (creada por db-init en desarrollo):
se migra una vez por sesión y cada prueba corre dentro de una transacción que se revierte al final.
"""

import os

# Antes de importar la aplicación: la configuración se lee del entorno y se cachea.
os.environ["APP_ENV"] = "test"
os.environ["DB_NAME"] = os.environ.get("TEST_DB_NAME") or f"{os.environ.get('DB_NAME', 'planiq')}_test"

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.session import build_engine
from app.modules.audit.listener import register_audit_listeners

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

# Igual que en la API y el worker: toda escritura del ORM queda auditada.
register_audit_listeners()


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    eng = build_engine(get_settings())
    with eng.begin() as conn:
        cfg = Config(str(ALEMBIC_INI))
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    with engine.connect() as conn:
        trans = conn.begin()
        yield conn
        trans.rollback()


@pytest.fixture
def session_factory(connection: Connection) -> sessionmaker[Session]:
    """Sesiones sobre la conexión de la prueba: sus commits son savepoints y todo se revierte al final."""
    return sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", autoflush=False, expire_on_commit=False
    )


@pytest.fixture
def db_session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as session:
        yield session
