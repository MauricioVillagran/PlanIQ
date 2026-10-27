from datetime import time

from pydantic import BaseModel, Field

from app.core.maintainer import MaintainerOut, VersionedUpdate
from app.core.maintainer.schemas import StrictInput


class ShiftCreate(StrictInput):
    plant_id: int
    name: str = Field(min_length=1, max_length=50, examples=["Noche"])
    start_time: time = Field(description="Hora local de la planta, HH:MM", examples=["20:00"])
    end_time: time = Field(
        description="Si es menor o igual al inicio, el turno cruza la medianoche", examples=["08:00"]
    )
    sort_order: int = Field(default=0, ge=0, le=99)


class ShiftUpdate(VersionedUpdate):
    """La planta de un turno no cambia: se desactiva y se crea en la otra planta."""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    start_time: time | None = None
    end_time: time | None = None
    sort_order: int | None = Field(default=None, ge=0, le=99)


class ShiftOut(MaintainerOut):
    plant_id: int
    name: str
    start_time: time
    end_time: time
    crosses_midnight: bool
    duration_minutes: int
    sort_order: int


class CoverageGap(BaseModel):
    start: time
    end: time


class ShiftCoverageOut(BaseModel):
    plant_id: int
    full_coverage_required: bool = Field(description="Parámetro shifts.full_coverage vigente para la planta")
    covered: bool = Field(description="True si los turnos activos cubren las 24 horas")
    gaps: list[CoverageGap]
    covered_minutes: int
