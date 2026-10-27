"""Engine de SQLAlchemy, fábrica de sesiones y dependencia de FastAPI."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


def build_url(settings: Settings) -> URL:
    return URL.create(
        "mssql+pyodbc",
        username=settings.db_user,
        password=settings.db_password.get_secret_value(),
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        query={
            "driver": settings.db_odbc_driver,
            "Encrypt": "yes",
            "TrustServerCertificate": "yes" if settings.db_trust_server_certificate else "no",
        },
    )


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        build_url(settings),
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        # Inserciones masivas rápidas (cargas Excel vía staging).
        fast_executemany=True,
    )


@lru_cache
def get_engine() -> Engine:
    return build_engine(get_settings())


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Una sesión por solicitud. El servicio controla la transacción (`with session.begin():`)."""
    with get_sessionmaker()() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
