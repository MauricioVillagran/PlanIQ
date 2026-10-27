"""Servicio genérico de mantenedor. Los módulos lo heredan y redefinen los ganchos cuando necesitan
reglas propias (por ejemplo, encriptar la contraseña al crear un usuario)."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import BusinessRuleError, ConflictError, FieldError, NotFoundError
from app.core.maintainer.schemas import StrictInput, VersionedUpdate
from app.core.maintainer.spec import MaintainerSpec
from app.core.pagination import PageParams
from app.modules.auth.dependencies import CurrentUser, ensure_plant_access

MAX_EXPORT_ROWS = 50_000

Status = Literal["active", "inactive", "all"]


@dataclass(frozen=True)
class ListQuery:
    q: str | None = None
    status: Status = "all"
    sort: str | None = None
    filters: dict[str, Any] = field(default_factory=dict)


def _is_unique_violation(exc: IntegrityError) -> bool:
    # SQL Server: 2627 = restricción UNIQUE / PK, 2601 = índice único.
    text = str(exc.orig)
    return "2627" in text or "2601" in text


class MaintainerService:
    def __init__(self, session: Session, user: CurrentUser, spec: MaintainerSpec) -> None:
        self.session = session
        self.user = user
        self.spec = spec
        self.model = spec.model

    # --- Consultas -----------------------------------------------------------------------

    def _column(self, name: str) -> Any:
        return getattr(self.model, name)

    def base_query(self) -> Select[Any]:
        """Consulta base: aplica el acceso por planta. Los módulos pueden agregar joins o condiciones."""
        query = select(self.model)
        if self.spec.plant_field and self.user.plant_ids is not None:
            query = query.where(self._column(self.spec.plant_field).in_(self.user.plant_ids))
        return query

    def _apply_list_query(self, query: Select[Any], list_query: ListQuery) -> Select[Any]:
        # SQL Server no tiene booleano nativo: la columna sola se traduce a "= 1" y su negación a "= 0".
        if list_query.status == "active":
            query = query.where(self._column("is_active"))
        elif list_query.status == "inactive":
            query = query.where(~self._column("is_active"))
        if list_query.q and self.spec.search_fields:
            term = list_query.q.strip()
            conditions: list[ColumnElement[bool]] = [
                self._column(f).contains(term, autoescape=True) for f in self.spec.search_fields
            ]
            query = query.where(or_(*conditions))
        for name, value in list_query.filters.items():
            if value is not None:
                query = query.where(self._column(name) == value)
        return query

    def _order(self, query: Select[Any], sort: str | None) -> Select[Any]:
        sort = sort or self.spec.default_sort
        descending = sort.startswith("-")
        name = sort.lstrip("-")
        if name not in self.spec.sort_fields:
            raise BusinessRuleError(
                f"No se puede ordenar por '{name}'.",
                code="invalid_sort",
                details={"allowed": list(self.spec.sort_fields)},
            )
        column = self._column(name)
        return query.order_by(column.desc() if descending else column.asc(), self._column("id").asc())

    def list(self, list_query: ListQuery, params: PageParams) -> tuple[Sequence[Any], int]:
        query = self._apply_list_query(self.base_query(), list_query)
        total = self.session.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
        rows = self.session.scalars(
            self._order(query, list_query.sort).offset(params.offset).limit(params.page_size)
        ).all()
        return rows, int(total)

    def export_rows(self, list_query: ListQuery) -> Sequence[Any]:
        query = self._order(self._apply_list_query(self.base_query(), list_query), list_query.sort)
        rows = self.session.scalars(query.limit(MAX_EXPORT_ROWS + 1)).all()
        if len(rows) > MAX_EXPORT_ROWS:
            raise BusinessRuleError(
                f"La exportación supera {MAX_EXPORT_ROWS:,} filas. Aplique filtros.".replace(",", "."),
                code="export_too_large",
            )
        return rows

    def get(self, item_id: int) -> Any:
        """Un registro fuera del alcance de plantas del usuario se informa como inexistente."""
        obj = self.session.scalar(self.base_query().where(self._column("id") == item_id))
        if obj is None:
            raise NotFoundError(f"No existe {self.spec.label} con id {item_id}.")
        return obj

    # --- Escrituras ----------------------------------------------------------------------

    def create(self, data: StrictInput) -> Any:
        values = data.model_dump()
        obj = self.model()
        self.apply(obj, values, creating=True)
        self._check_required(obj)
        self._check_plant_access(obj, creating=True)
        self.validate(obj, creating=True)
        self._check_unique(obj)
        self.session.add(obj)
        self._commit(obj)
        return obj

    def update(self, item_id: int, data: VersionedUpdate) -> Any:
        obj = self.get(item_id)
        if obj.row_version.hex() != data.row_version:
            raise self._conflict(obj)
        values = data.model_dump(exclude_unset=True, exclude={"row_version"})
        self.apply(obj, values, creating=False)
        self._check_required(obj)
        self._check_plant_access(obj, creating=False)
        self.validate(obj, creating=False)
        self._check_unique(obj)
        self._commit(obj)
        return obj

    def set_active(self, item_id: int, active: bool) -> Any:
        obj = self.get(item_id)
        if obj.is_active != active:
            self.before_set_active(obj, active)
            obj.is_active = active
            self._commit(obj)
        return obj

    # --- Ganchos para los módulos --------------------------------------------------------

    def apply(self, obj: Any, values: dict[str, Any], *, creating: bool) -> None:
        """Copia los valores validados al modelo. Redefinir para campos calculados o relaciones."""
        for key, value in values.items():
            setattr(obj, key, value)

    def validate(self, obj: Any, *, creating: bool) -> None:
        """Reglas de negocio antes de guardar. Lanzar BusinessRuleError con field_errors."""

    def before_set_active(self, obj: Any, active: bool) -> None:
        """Reglas para activar o desactivar (por ejemplo, impedir desactivar un rol base)."""

    # --- Internos ------------------------------------------------------------------------

    def _check_required(self, obj: Any) -> None:
        """Un PATCH parcial no puede dejar en null una columna obligatoria (evita un error de la base)."""
        missing = [
            column.key
            for column in self.model.__table__.columns
            if not column.nullable
            and not column.primary_key
            and column.default is None
            and column.server_default is None
            and getattr(obj, column.key, None) is None
        ]
        if missing:
            raise BusinessRuleError(
                "Hay campos obligatorios vacíos.",
                code="required",
                field_errors=[
                    FieldError(field=m, message="Campo obligatorio.", code="missing") for m in missing
                ],
            )

    def _check_plant_access(self, obj: Any, *, creating: bool) -> None:
        field_name = self.spec.plant_field
        # En el maestro de plantas la planta es el propio registro: al crearla aún no tiene id.
        if field_name is None or (field_name == "id" and creating):
            return
        plant_id = getattr(obj, field_name)
        if plant_id is not None:
            ensure_plant_access(self.user, plant_id)

    def _check_unique(self, obj: Any) -> None:
        errors: list[FieldError] = []
        for name, label in self.spec.unique_fields.items():
            value = getattr(obj, name)
            if value is None:
                continue
            query = select(self._column("id")).where(self._column(name) == value)
            if obj.id is not None:
                query = query.where(self._column("id") != obj.id)
            if self.session.scalar(query.limit(1)) is not None:
                errors.append(
                    FieldError(
                        field=name, message=f"Ya existe {self.spec.label} con ese {label}.", code="unique"
                    )
                )
        if errors:
            raise BusinessRuleError("Hay valores repetidos.", code="duplicate", field_errors=errors)

    def _conflict(self, obj: Any) -> ConflictError:
        self.session.refresh(obj)
        return ConflictError(details={"current": self.spec.out(obj).model_dump(mode="json")})

    def _commit(self, obj: Any) -> None:
        try:
            self.session.commit()
        except StaleDataError:
            self.session.rollback()
            raise self._conflict(obj) from None
        except IntegrityError as exc:
            self.session.rollback()
            if _is_unique_violation(exc):
                raise ConflictError("Otro usuario registró el mismo valor.", code="duplicate") from exc
            raise
        self.session.refresh(obj)
