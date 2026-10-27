from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.core.maintainer import MaintainerOut, VersionedUpdate
from app.core.maintainer.schemas import StrictInput

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
USERNAME_PATTERN = r"^[a-z0-9._-]{3,50}$"

Lower = BeforeValidator(lambda v: v.lower() if isinstance(v, str) else v)
Username = Annotated[str, Lower, Field(pattern=USERNAME_PATTERN, examples=["mperez"])]
Email = Annotated[str, Lower, Field(max_length=254, pattern=EMAIL_PATTERN, examples=["mperez@example.com"])]


class UserCreate(StrictInput):
    username: Username
    email: Email
    full_name: str = Field(min_length=1, max_length=150)
    role_ids: list[int] = Field(min_length=1, description="Al menos un rol")
    plant_ids: list[int] = Field(
        default_factory=list, description="Plantas con acceso (no aplica con plants.all)"
    )


class UserUpdate(VersionedUpdate):
    """El nombre de usuario no cambia. La contraseña se gestiona con reset-password."""

    email: Email | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    role_ids: list[int] | None = Field(default=None, min_length=1)
    plant_ids: list[int] | None = None


class RefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class UserOut(MaintainerOut):
    username: str
    email: str
    full_name: str
    must_change_password: bool
    locked: bool
    locked_at: datetime | None
    last_login_at: datetime | None
    roles: list[RefOut]
    plants: list[RefOut]
    temporary_password: str | None = Field(
        default=None,
        description=(
            "Solo al crear el usuario: clave temporal que debe cambiar en su primer ingreso. "
            "No se vuelve a mostrar."
        ),
    )


class TemporaryPasswordOut(BaseModel):
    temporary_password: str = Field(description="Clave temporal; el usuario debe cambiarla al ingresar")
