from datetime import date
from typing import Literal

from pydantic import Field

from app.core.maintainer import MaintainerOut, VersionedUpdate
from app.core.maintainer.schemas import StrictInput

ValueTypeLiteral = Literal["int", "decimal", "bool", "text"]
KEY_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$"


class ParameterCreate(StrictInput):
    key: str = Field(max_length=100, pattern=KEY_PATTERN, examples=["harvest.avg_weight_kg.max"])
    plant_id: int | None = Field(default=None, description="Null = valor global para todas las plantas")
    value_type: ValueTypeLiteral
    value: str = Field(max_length=400, description="Decimales con punto o coma; bool: true/false")
    unit: str | None = Field(default=None, max_length=30, examples=["kg"])
    description: str | None = Field(default=None, max_length=400)
    valid_from: date | None = Field(default=None, description="Desde (incluido); null = sin límite")
    valid_to: date | None = Field(default=None, description="Hasta (excluido); null = sin límite")


class ParameterUpdate(VersionedUpdate):
    """Clave, planta y tipo no cambian: para eso se crea otro parámetro."""

    value: str | None = Field(default=None, max_length=400)
    unit: str | None = Field(default=None, max_length=30)
    description: str | None = Field(default=None, max_length=400)
    valid_from: date | None = None
    valid_to: date | None = None


class ParameterOut(MaintainerOut):
    key: str
    plant_id: int | None
    value_type: str
    value: str
    unit: str | None
    description: str | None
    valid_from: date | None
    valid_to: date | None
