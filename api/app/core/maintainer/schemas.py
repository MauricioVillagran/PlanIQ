"""Esquemas base que comparten todos los mantenedores."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

ROW_VERSION_PATTERN = r"^[0-9a-f]{16}$"


class MaintainerOut(BaseModel):
    """Campos comunes de salida. `row_version` se devuelve en hexadecimal y se reenvía al editar."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    row_version: str = Field(description="Versión de la fila; enviarla sin cambios en el PATCH")
    created_at: datetime
    updated_at: datetime | None

    @field_validator("row_version", mode="before")
    @classmethod
    def _row_version_hex(cls, value: object) -> object:
        return value.hex() if isinstance(value, bytes) else value


class StrictInput(BaseModel):
    """Entrada de mantenedor: rechaza campos desconocidos y recorta espacios en los textos."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class VersionedUpdate(StrictInput):
    """Base de los esquemas de edición: todos los campos opcionales más la versión leída."""

    row_version: str = Field(
        pattern=ROW_VERSION_PATTERN,
        description="row_version recibido al leer el registro; si cambió, la API responde 409",
    )
