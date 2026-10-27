"""Columnas comunes de las tablas (convenciones de la sección 8 de la especificación)."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, FetchedValue, Identity, func, true
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.db.types import UtcDateTime


class IdMixin:
    id: Mapped[int] = mapped_column(BigInteger, Identity(start=1, increment=1), primary_key=True)


class AuditMixin:
    """Quién y cuándo creó y modificó el registro.

    `created_by` y `updated_by` son ids de `core.users` sin FK, para no acoplar cada tabla
    a la de usuarios; los usuarios nunca se borran (solo se desactivan).
    """

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.sysutcdatetime(), nullable=False
    )
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime | None] = mapped_column(UtcDateTime, onupdate=func.sysutcdatetime())
    updated_by: Mapped[int | None] = mapped_column(BigInteger)


class ActiveMixin:
    """Borrado lógico: los registros con historia se desactivan en vez de borrarse."""

    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True, nullable=False)


class RowVersionMixin:
    """Concurrencia optimista con `rowversion` de SQL Server.

    SQLAlchemy incluye la versión leída en el WHERE de cada UPDATE; si otro usuario modificó la fila,
    el UPDATE no afecta filas y se lanza `StaleDataError`, que la API responde como 409.
    """

    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION, nullable=False, server_default=FetchedValue(), server_onupdate=FetchedValue()
    )

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, Any]:  # noqa: N805 (declared_attr recibe la clase)
        return {
            "version_id_col": cls.__table__.c.row_version,  # type: ignore[attr-defined]
            "version_id_generator": False,
            "eager_defaults": True,
        }
