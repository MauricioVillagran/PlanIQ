"""Entorno de Alembic: usa la configuración de la aplicación y el registro de modelos."""

from logging.config import fileConfig

from alembic import context

from app.core.config import get_settings
from app.db.migration_support import compare_type
from app.db.models import Base
from app.db.session import build_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    from app.db.session import build_url

    context.configure(
        url=build_url(get_settings()).render_as_string(hide_password=False),
        target_metadata=target_metadata,
        include_schemas=True,
        literal_binds=True,
        compare_type=compare_type,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Las pruebas pasan su propia conexión (base de test) por config.attributes.
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = build_engine(get_settings())
    with engine.connect() as conn:
        _run(conn)
    engine.dispose()


def _run(connection: object) -> None:
    context.configure(
        connection=connection,  # type: ignore[arg-type]
        target_metadata=target_metadata,
        include_schemas=True,
        compare_type=compare_type,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
