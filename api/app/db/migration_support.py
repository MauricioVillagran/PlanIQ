"""Ajustes de Alembic para SQL Server, compartidos por env.py y las pruebas."""

from typing import Any

from sqlalchemy.dialects import mssql
from sqlalchemy.types import TypeEngine


def compare_type(
    _context: Any,
    _inspected_column: Any,
    _metadata_column: Any,
    inspected_type: TypeEngine[Any],
    metadata_type: TypeEngine[Any],
) -> bool | None:
    """SQL Server reporta `rowversion` con su nombre de catálogo `timestamp`: no es un cambio de tipo."""
    if isinstance(metadata_type, mssql.TIMESTAMP) and isinstance(inspected_type, mssql.TIMESTAMP):
        return False
    return None  # comparación por defecto de Alembic
