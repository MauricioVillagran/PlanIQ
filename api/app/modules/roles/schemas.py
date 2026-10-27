from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.maintainer import MaintainerOut, VersionedUpdate
from app.core.maintainer.schemas import StrictInput


class RoleCreate(StrictInput):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,49}$", examples=["supervisor_frigorifico"])
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=400)
    permissions: list[str] = Field(
        default_factory=list, description="Códigos de permiso, por ejemplo plan.view"
    )


class RoleUpdate(VersionedUpdate):
    """El código no cambia. `permissions` reemplaza la lista completa del rol."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=400)
    permissions: list[str] | None = None


class RoleOut(MaintainerOut):
    code: str
    name: str
    description: str | None
    is_system: bool
    permissions: list[str]

    @field_validator("permissions", mode="before")
    @classmethod
    def _codes(cls, value: object) -> object:
        if isinstance(value, list):
            return sorted(p if isinstance(p, str) else p.code for p in value)
        return value


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    module: str
    description: str | None
