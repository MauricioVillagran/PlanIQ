"""Mantenedor de plantas (sección 5.1). Ninguna planta viene precargada: todas se crean aquí.

Es la implementación de referencia del patrón de mantenedor.
"""

from app.core.maintainer import ExportColumn, MaintainerSpec, build_maintainer_router
from app.modules.plants.models import Plant
from app.modules.plants.schemas import PlantCreate, PlantOut, PlantUpdate

PLANT_TYPE_LABELS = {"own": "Propia", "contract": "Maquila"}

spec = MaintainerSpec(
    model=Plant,
    resource="plants",
    label="planta",
    out_schema=PlantOut,
    create_schema=PlantCreate,
    update_schema=PlantUpdate,
    view_permission="masters.view",
    edit_permission="masters.edit",
    search_fields=("code", "name", "location"),
    filters={"plant_type": str},
    sort_fields=("code", "name", "plant_type", "created_at"),
    default_sort="name",
    unique_fields={"code": "código"},
    plant_field="id",
    export_columns=(
        ExportColumn("Código", "code", 12),
        ExportColumn("Nombre", "name", 30),
        ExportColumn("Tipo", lambda p: PLANT_TYPE_LABELS.get(p.plant_type, p.plant_type), 12),
        ExportColumn("Ubicación", "location", 25),
        ExportColumn("Zona horaria", "timezone", 20),
        ExportColumn("Activa", "is_active", 8),
        ExportColumn("Creada", "created_at", 18),
        ExportColumn("Modificada", "updated_at", 18),
    ),
)

router = build_maintainer_router(spec)
