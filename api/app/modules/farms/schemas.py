from pydantic import Field

from app.core.maintainer import MaintainerOut, VersionedUpdate
from app.core.maintainer.schemas import StrictInput


class FarmCenterCreate(StrictInput):
    code: str = Field(min_length=1, max_length=20, examples=["CH-101"])
    name: str = Field(min_length=1, max_length=150, examples=["Centro Huelmo"])
    zone: str | None = Field(default=None, max_length=100, examples=["Barrio 3A"])


class FarmCenterUpdate(VersionedUpdate):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    zone: str | None = Field(default=None, max_length=100)


class FarmCenterOut(MaintainerOut):
    code: str
    name: str
    zone: str | None


class CageCreate(StrictInput):
    farm_center_id: int
    code: str = Field(min_length=1, max_length=20, examples=["J-104"])


class CageUpdate(VersionedUpdate):
    """El centro de una jaula no cambia: se desactiva y se crea en el otro centro."""

    code: str | None = Field(default=None, min_length=1, max_length=20)


class CageOut(MaintainerOut):
    farm_center_id: int
    farm_center_code: str
    farm_center_name: str
    code: str


class HoldingCageCreate(StrictInput):
    plant_id: int
    code: str = Field(min_length=1, max_length=20, examples=["A-1"])
    capacity_fish: int = Field(gt=0, le=10_000_000, description="Capacidad en peces")


class HoldingCageUpdate(VersionedUpdate):
    """La planta de un acopio no cambia."""

    code: str | None = Field(default=None, min_length=1, max_length=20)
    capacity_fish: int | None = Field(default=None, gt=0, le=10_000_000)


class HoldingCageOut(MaintainerOut):
    plant_id: int
    code: str
    capacity_fish: int
