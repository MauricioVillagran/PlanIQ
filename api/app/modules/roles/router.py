"""Mantenedor de roles con su matriz de permisos (sección 3) y catálogo de permisos."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.errors import BusinessRuleError, FieldError
from app.core.maintainer import ExportColumn, MaintainerService, MaintainerSpec, build_maintainer_router
from app.db.session import SessionDep
from app.modules.auth.dependencies import CurrentUser, require_permission
from app.modules.roles.models import Permission, Role
from app.modules.roles.schemas import PermissionOut, RoleCreate, RoleOut, RoleUpdate
from app.modules.users.models import User
from app.modules.users.router import ADMIN_PERMISSION


def _admins_through_other_roles(session: Any, role_id: int) -> int:
    """Usuarios activos que conservan users.admin por algún rol distinto de `role_id`."""
    users = session.scalars(select(User).where(User.is_active)).all()
    return sum(
        1
        for u in users
        if any(
            p.code == ADMIN_PERMISSION
            for r in u.roles
            if r.is_active and r.id != role_id
            for p in r.permissions
        )
    )


class RoleService(MaintainerService):
    def apply(self, obj: Any, values: dict[str, Any], *, creating: bool) -> None:
        codes = values.pop("permissions", None)
        super().apply(obj, values, creating=creating)
        if creating:
            obj.is_system = False
        if codes is not None:
            wanted = list(dict.fromkeys(codes))
            found = (
                list(self.session.scalars(select(Permission).where(Permission.code.in_(wanted))))
                if wanted
                else []
            )
            missing = sorted(set(wanted) - {p.code for p in found})
            if missing:
                raise BusinessRuleError(
                    f"Permisos inexistentes: {', '.join(missing)}.",
                    code="invalid_reference",
                    field_errors=[
                        FieldError(field="permissions", message="Permiso inválido.", code="invalid")
                    ],
                )
            obj.permissions = found

    def validate(self, obj: Any, *, creating: bool) -> None:
        if creating:
            return
        loses_admin = not any(p.code == ADMIN_PERMISSION for p in obj.permissions)
        if loses_admin and _admins_through_other_roles(self.session, obj.id) == 0:
            raise BusinessRuleError(
                "Debe quedar al menos un usuario activo con permiso para administrar usuarios.",
                code="last_admin",
            )

    def before_set_active(self, obj: Any, active: bool) -> None:
        if active:
            return
        if obj.is_system:
            raise BusinessRuleError("Los roles base no se pueden desactivar.", code="system_role")
        if any(p.code == ADMIN_PERMISSION for p in obj.permissions) and (
            _admins_through_other_roles(self.session, obj.id) == 0
        ):
            raise BusinessRuleError(
                "Debe quedar al menos un usuario activo con permiso para administrar usuarios.",
                code="last_admin",
            )


spec = MaintainerSpec(
    model=Role,
    resource="roles",
    label="rol",
    out_schema=RoleOut,
    create_schema=RoleCreate,
    update_schema=RoleUpdate,
    view_permission=ADMIN_PERMISSION,
    edit_permission=ADMIN_PERMISSION,
    search_fields=("code", "name", "description"),
    sort_fields=("name", "code", "created_at"),
    default_sort="name",
    unique_fields={"code": "código", "name": "nombre"},
    export_columns=(
        ExportColumn("Código", "code", 18),
        ExportColumn("Nombre", "name", 28),
        ExportColumn("Rol base", "is_system", 10),
        ExportColumn("Permisos", lambda r: ", ".join(sorted(p.code for p in r.permissions)), 60),
        ExportColumn("Activo", "is_active", 8),
    ),
)

router = build_maintainer_router(spec, RoleService)

permissions_router = APIRouter(prefix="/permissions", tags=["roles"])


@permissions_router.get("", response_model=list[PermissionOut], summary="Catálogo de permisos")
def list_permissions(
    session: SessionDep,
    _user: Annotated[CurrentUser, Depends(require_permission(ADMIN_PERMISSION))],
) -> Any:
    return session.scalars(select(Permission).order_by(Permission.module, Permission.code)).all()
