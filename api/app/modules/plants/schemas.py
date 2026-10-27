from typing import Literal
from zoneinfo import available_timezones

from pydantic import Field, field_validator

from app.core.maintainer import MaintainerOut, VersionedUpdate
from app.core.maintainer.schemas import StrictInput

PlantTypeLiteral = Literal["own", "contract"]

_TIMEZONES = available_timezones()


def _check_timezone(value: str | None) -> str | None:
    if value is not None and value not in _TIMEZONES:
        raise ValueError("Zona horaria desconocida (formato IANA, por ejemplo America/Santiago).")
    return value


class PlantCreate(StrictInput):
    code: str = Field(min_length=1, max_length=20, examples=["VS"])
    name: str = Field(min_length=1, max_length=150, examples=["Planta Victoria Sur"])
    plant_type: PlantTypeLiteral = Field(description="own = propia, contract = maquila")
    location: str | None = Field(default=None, max_length=200)
    timezone: str = Field(default="America/Santiago", max_length=64)

    _tz = field_validator("timezone")(_check_timezone)


class PlantUpdate(VersionedUpdate):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    plant_type: PlantTypeLiteral | None = None
    location: str | None = Field(default=None, max_length=200)
    timezone: str | None = Field(default=None, max_length=64)

    _tz = field_validator("timezone")(_check_timezone)


class PlantOut(MaintainerOut):
    code: str
    name: str
    plant_type: str
    location: str | None
    timezone: str
