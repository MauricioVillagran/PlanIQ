"""Ajustes de Alembic para SQL Server, compartidos por env.py y las pruebas."""

from typing import Any

from sqlalchemy.dialects import mssql
from sqlalchemy.types import TypeEngine

from app.db.types import UtcDateTime


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


def render_item(type_: str, obj: Any, autogen_context: Any) -> str | bool:
    """Las migraciones generadas no deben importar tipos de la aplicación: UtcDateTime → DATETIME2(3)."""
    if type_ == "type" and isinstance(obj, UtcDateTime):
        autogen_context.imports.add("from sqlalchemy.dialects import mssql")
        return f"mssql.DATETIME2(precision={obj.impl.precision})"
    return False  # render por defecto


# Tablas temporales: el historial vive en este esquema y las columnas de período son ocultas. Los
# crea SQL explícito en las migraciones y no tienen modelo, así que la comparación los ignora.
HISTORY_SCHEMA = "plan_history"
PERIOD_COLUMNS = frozenset({"valid_from", "valid_to"})


def include_name(name: str | None, type_: str, parent_names: dict[str, Any]) -> bool:
    return not (type_ == "schema" and name == HISTORY_SCHEMA)


def include_object(obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any) -> bool:
    return not (type_ == "column" and reflected and compare_to is None and name in PERIOD_COLUMNS)
