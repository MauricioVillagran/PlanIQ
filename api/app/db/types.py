"""Tipos de columna comunes."""

from datetime import UTC, datetime

from sqlalchemy import Dialect, TypeDecorator
from sqlalchemy.dialects import mssql


class UtcDateTime(TypeDecorator[datetime]):
    """Fecha-hora en UTC: se guarda en DATETIME2(3) sin zona y se lee como `datetime` con zona UTC.

    Rechaza valores sin zona para que nunca se guarde una hora local por error.
    """

    impl = mssql.DATETIME2(precision=3)  # type: ignore[no-untyped-call]
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("UtcDateTime requiere un datetime con zona horaria")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)
