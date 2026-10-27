"""Mantenedores de cultivo: centros, jaulas y jaulas de acopio (Fase 1, ADR 0005)."""

from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from app.core.errors import BusinessRuleError, FieldError
from app.core.maintainer import ExportColumn, MaintainerService, MaintainerSpec, build_maintainer_router
from app.modules.farms.models import Cage, FarmCenter, HoldingCage
from app.modules.farms.schemas import (
    CageCreate,
    CageOut,
    CageUpdate,
    FarmCenterCreate,
    FarmCenterOut,
    FarmCenterUpdate,
    HoldingCageCreate,
    HoldingCageOut,
    HoldingCageUpdate,
)
from app.modules.plants.models import Plant

VIEW = "masters.view"
EDIT = "farms.edit"


def _require_active(service: MaintainerService, model: Any, item_id: int, field: str, label: str) -> None:
    if not service.session.scalar(select(model.id).where(model.id == item_id, model.is_active)):
        raise BusinessRuleError(
            f"{label} no existe o está inactivo.",
            code="invalid_reference",
            field_errors=[FieldError(field=field, message=f"{label} inválido.", code="invalid")],
        )


def _unique_within(service: MaintainerService, obj: Any, parent_field: str, message: str) -> None:
    """Código único dentro de su padre (centro o planta)."""
    model = type(obj)
    query = select(model.id).where(
        getattr(model, parent_field) == getattr(obj, parent_field), model.code == obj.code
    )
    if obj.id is not None:
        query = query.where(model.id != obj.id)
    if service.session.scalar(query.limit(1)) is not None:
        raise BusinessRuleError(
            "Hay valores repetidos.",
            code="duplicate",
            field_errors=[FieldError(field="code", message=message, code="unique")],
        )


class CageService(MaintainerService):
    def validate(self, obj: Any, *, creating: bool) -> None:
        if creating:
            _require_active(self, FarmCenter, obj.farm_center_id, "farm_center_id", "El centro")
        _unique_within(self, obj, "farm_center_id", "Ya existe una jaula con ese código en el centro.")


class HoldingCageService(MaintainerService):
    def validate(self, obj: Any, *, creating: bool) -> None:
        if creating:
            _require_active(self, Plant, obj.plant_id, "plant_id", "La planta")
        _unique_within(self, obj, "plant_id", "Ya existe una jaula de acopio con ese código en la planta.")


farm_centers_spec = MaintainerSpec(
    model=FarmCenter,
    resource="farm-centers",
    label="centro",
    out_schema=FarmCenterOut,
    create_schema=FarmCenterCreate,
    update_schema=FarmCenterUpdate,
    view_permission=VIEW,
    edit_permission=EDIT,
    search_fields=("code", "name", "zone"),
    sort_fields=("code", "name", "zone", "created_at"),
    default_sort="name",
    unique_fields={"code": "código"},
    export_columns=(
        ExportColumn("Código", "code", 14),
        ExportColumn("Centro", "name", 30),
        ExportColumn("Zona o barrio", "zone", 20),
        ExportColumn("Activo", "is_active", 8),
    ),
    tags=("farms",),
)

cages_spec = MaintainerSpec(
    model=Cage,
    resource="cages",
    label="jaula",
    out_schema=CageOut,
    create_schema=CageCreate,
    update_schema=CageUpdate,
    view_permission=VIEW,
    edit_permission=EDIT,
    search_fields=("code",),
    filters={"farm_center_id": int},
    sort_fields=("code", "farm_center_id", "created_at"),
    default_sort="code",
    export_columns=(
        ExportColumn("Centro", "farm_center_code", 14),
        ExportColumn("Nombre del centro", "farm_center_name", 30),
        ExportColumn("Jaula", "code", 12),
        ExportColumn("Activa", "is_active", 8),
    ),
    tags=("farms",),
)

holding_cages_spec = MaintainerSpec(
    model=HoldingCage,
    resource="holding-cages",
    label="jaula de acopio",
    out_schema=HoldingCageOut,
    create_schema=HoldingCageCreate,
    update_schema=HoldingCageUpdate,
    view_permission=VIEW,
    edit_permission=EDIT,
    search_fields=("code",),
    filters={"plant_id": int},
    sort_fields=("code", "capacity_fish", "created_at"),
    default_sort="code",
    plant_field="plant_id",
    export_columns=(
        ExportColumn("Planta", lambda h: h.plant.code, 12),
        ExportColumn("Acopio", "code", 12),
        ExportColumn("Capacidad (peces)", "capacity_fish", 18),
        ExportColumn("Activa", "is_active", 8),
    ),
    tags=("farms",),
)

router = APIRouter()
router.include_router(build_maintainer_router(farm_centers_spec))
router.include_router(build_maintainer_router(cages_spec, CageService))
router.include_router(build_maintainer_router(holding_cages_spec, HoldingCageService))
