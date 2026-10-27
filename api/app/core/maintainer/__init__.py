"""Patrón común de mantenedores: listado, detalle, alta, edición con concurrencia, activación,
historial y exportación a Excel, construido una vez y configurado por recurso."""

from app.core.maintainer.router import build_maintainer_router
from app.core.maintainer.schemas import MaintainerOut, VersionedUpdate
from app.core.maintainer.service import ListQuery, MaintainerService
from app.core.maintainer.spec import ExportColumn, MaintainerSpec

__all__ = [
    "ExportColumn",
    "ListQuery",
    "MaintainerOut",
    "MaintainerService",
    "MaintainerSpec",
    "VersionedUpdate",
    "build_maintainer_router",
]
