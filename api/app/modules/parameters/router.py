"""Mantenedor de parámetros (sección 5.1): valores globales o por planta, con tipo, unidad y vigencia."""

from datetime import date
from typing import Any

from sqlalchemy import Select, or_, select

from app.core.errors import BusinessRuleError, FieldError, PermissionDeniedError
from app.core.maintainer import ExportColumn, MaintainerService, MaintainerSpec, build_maintainer_router
from app.modules.auth.dependencies import ALL_PLANTS_PERMISSION
from app.modules.parameters.models import Parameter
from app.modules.parameters.schemas import ParameterCreate, ParameterOut, ParameterUpdate
from app.modules.parameters.values import normalize_value
from app.modules.plants.models import Plant


def _overlaps(a_from: date | None, a_to: date | None, b_from: date | None, b_to: date | None) -> bool:
    """Vigencias [desde, hasta) con None como sin límite."""
    return (a_to is None or b_from is None or b_from < a_to) and (
        b_to is None or a_from is None or a_from < b_to
    )


class ParameterService(MaintainerService):
    def base_query(self) -> Select[Any]:
        query = select(Parameter)
        # Los globales los ven todos; los de planta, solo quien tiene acceso a esa planta.
        if self.user.plant_ids is not None:
            query = query.where(
                or_(Parameter.plant_id.is_(None), Parameter.plant_id.in_(self.user.plant_ids))
            )
        return query

    def apply(self, obj: Any, values: dict[str, Any], *, creating: bool) -> None:
        if "value" in values and values["value"] is not None:
            value_type = values.get("value_type") or obj.value_type
            try:
                values["value"] = normalize_value(value_type, values["value"])
            except ValueError as exc:
                raise BusinessRuleError(
                    "El valor no corresponde al tipo.",
                    code="invalid_value",
                    field_errors=[FieldError(field="value", message=str(exc), code="invalid")],
                ) from None
        super().apply(obj, values, creating=creating)

    def validate(self, obj: Any, *, creating: bool) -> None:
        if obj.plant_id is None and not self.user.has_permission(ALL_PLANTS_PERMISSION):
            raise PermissionDeniedError(
                "Solo quien tiene acceso a todas las plantas puede editar parámetros globales.",
                code="global_parameter_denied",
            )
        if obj.plant_id is not None and not self.session.scalar(
            select(Plant.id).where(Plant.id == obj.plant_id, Plant.is_active)
        ):
            raise BusinessRuleError(
                "La planta no existe o está inactiva.",
                code="invalid_plant",
                field_errors=[FieldError(field="plant_id", message="Planta inválida.", code="invalid")],
            )
        if obj.valid_from and obj.valid_to and obj.valid_from >= obj.valid_to:
            raise BusinessRuleError(
                "La vigencia no es válida.",
                code="invalid_validity",
                field_errors=[
                    FieldError(
                        field="valid_to", message="Debe ser posterior a la fecha desde.", code="invalid"
                    )
                ],
            )
        types = set(
            self.session.scalars(
                select(Parameter.value_type).where(Parameter.key == obj.key, Parameter.id != (obj.id or 0))
            )
        )
        if types and obj.value_type not in types:
            raise BusinessRuleError(
                f"El parámetro '{obj.key}' ya existe con tipo {', '.join(sorted(types))}.",
                code="value_type_mismatch",
                field_errors=[
                    FieldError(field="value_type", message="Tipo distinto al existente.", code="invalid")
                ],
            )
        if obj.is_active is not False:
            self._check_validity_overlap(obj)

    def before_set_active(self, obj: Any, active: bool) -> None:
        if active:
            self._check_validity_overlap(obj)

    def _check_validity_overlap(self, obj: Parameter) -> None:
        siblings = self.session.scalars(
            select(Parameter).where(
                Parameter.key == obj.key,
                Parameter.is_active,
                Parameter.id != (obj.id or 0),
                Parameter.plant_id.is_(None) if obj.plant_id is None else Parameter.plant_id == obj.plant_id,
            )
        ).all()
        if any(_overlaps(obj.valid_from, obj.valid_to, s.valid_from, s.valid_to) for s in siblings):
            raise BusinessRuleError(
                "Ya hay un valor vigente para este parámetro y alcance en esas fechas.",
                code="validity_overlap",
                field_errors=[FieldError(field="valid_from", message="Vigencia traslapada.", code="overlap")],
            )


spec = MaintainerSpec(
    model=Parameter,
    resource="parameters",
    label="parámetro",
    out_schema=ParameterOut,
    create_schema=ParameterCreate,
    update_schema=ParameterUpdate,
    view_permission="masters.view",
    edit_permission="parameters.edit",
    search_fields=("key", "description"),
    filters={"key": str, "plant_id": int},
    sort_fields=("key", "plant_id", "valid_from", "created_at"),
    default_sort="key",
    plant_field="plant_id",
    export_columns=(
        ExportColumn("Clave", "key", 30),
        ExportColumn("Planta (id)", "plant_id", 12),
        ExportColumn("Tipo", "value_type", 10),
        ExportColumn("Valor", "value", 16),
        ExportColumn("Unidad", "unit", 10),
        ExportColumn("Vigente desde", "valid_from", 14),
        ExportColumn("Vigente hasta", "valid_to", 14),
        ExportColumn("Descripción", "description", 40),
        ExportColumn("Activo", "is_active", 8),
    ),
)

router = build_maintainer_router(spec, ParameterService)
