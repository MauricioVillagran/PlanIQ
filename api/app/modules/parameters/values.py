"""Conversión y resolución de parámetros. Sin dependencias de FastAPI: lo usan servicios y procesos."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.parameters.models import Parameter, ValueType

ParameterValue = int | Decimal | bool | str

_TRUE = {"true", "1", "si", "sí"}
_FALSE = {"false", "0", "no"}


def normalize_value(value_type: str, raw: str) -> str:
    """Valida el texto según el tipo y lo devuelve en forma canónica. Acepta coma decimal."""
    text = raw.strip()
    if value_type == ValueType.INT:
        try:
            return str(int(text))
        except ValueError:
            raise ValueError("Debe ser un número entero.") from None
    if value_type == ValueType.DECIMAL:
        try:
            number = Decimal(text.replace(",", "."))
        except InvalidOperation:
            raise ValueError("Debe ser un número decimal.") from None
        if not number.is_finite():
            raise ValueError("Debe ser un número decimal.")
        return format(number.normalize(), "f")
    if value_type == ValueType.BOOL:
        lowered = text.lower()
        if lowered in _TRUE:
            return "true"
        if lowered in _FALSE:
            return "false"
        raise ValueError("Debe ser verdadero o falso (true/false).")
    if not text:
        raise ValueError("No puede estar vacío.")
    return text


def parse_value(value_type: str, stored: str) -> ParameterValue:
    if value_type == ValueType.INT:
        return int(stored)
    if value_type == ValueType.DECIMAL:
        return Decimal(stored)
    if value_type == ValueType.BOOL:
        return stored == "true"
    return stored


def _valid_on(on: date) -> tuple[Any, ...]:
    return (
        Parameter.is_active,
        or_(Parameter.valid_from.is_(None), Parameter.valid_from <= on),
        or_(Parameter.valid_to.is_(None), Parameter.valid_to > on),
    )


def get_parameter(
    session: Session, key: str, plant_id: int | None = None, on: date | None = None
) -> ParameterValue | None:
    """Valor vigente: primero el de la planta, si no el global. None si no está definido.

    Sin `on`, usa la fecha de hoy en la zona horaria por defecto (no la del servidor, que está en UTC).
    """
    day = on or datetime.now(ZoneInfo(get_settings().app_timezone)).date()
    candidates = session.scalars(
        select(Parameter)
        .where(Parameter.key == key, *_valid_on(day))
        .where(
            or_(Parameter.plant_id.is_(None), Parameter.plant_id == plant_id)
            if plant_id is not None
            else Parameter.plant_id.is_(None)
        )
    ).all()
    chosen = next((p for p in candidates if p.plant_id is not None), None) or next(iter(candidates), None)
    return parse_value(chosen.value_type, chosen.value) if chosen else None
