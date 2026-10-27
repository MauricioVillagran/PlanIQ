"""Configuración declarativa de un mantenedor."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from app.core.maintainer.schemas import MaintainerOut, StrictInput, VersionedUpdate


@dataclass(frozen=True)
class ExportColumn:
    header: str
    # Nombre de atributo del modelo o función que recibe el objeto y devuelve el valor de la celda.
    value: str | Callable[[Any], Any]
    width: int = 18


@dataclass(frozen=True)
class MaintainerSpec:
    model: type[Any]
    # Segmento de la URL: /api/v1/<resource>
    resource: str
    # Nombre en singular para mensajes y el nombre del archivo exportado ("planta").
    label: str
    out_schema: type[MaintainerOut]
    create_schema: type[StrictInput]
    update_schema: type[VersionedUpdate]
    view_permission: str
    edit_permission: str
    # Columnas de texto donde busca el parámetro `q`.
    search_fields: tuple[str, ...] = ()
    # Filtros exactos por query string: {nombre: tipo}.
    filters: dict[str, type] = field(default_factory=dict)
    sort_fields: tuple[str, ...] = ("id",)
    default_sort: str = "id"
    # Campos de valor único; {campo: etiqueta para el mensaje}.
    unique_fields: dict[str, str] = field(default_factory=dict)
    # Columna que identifica la planta del registro ("plant_id"; "id" en el propio maestro de plantas).
    # Con valor, el listado y el acceso se limitan a las plantas del usuario.
    plant_field: str | None = None
    export_columns: tuple[ExportColumn, ...] = ()
    tags: tuple[str, ...] = ()

    def out(self, obj: Any) -> BaseModel:
        return self.out_schema.model_validate(obj)
