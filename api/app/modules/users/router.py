"""Mantenedor de usuarios (sección 5.1): alta con clave temporal, roles, plantas, desactivación,
restablecimiento de contraseña y desbloqueo."""

import secrets
import string
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import func, select, update

from app.core.config import get_settings
from app.core.errors import BusinessRuleError, FieldError
from app.core.maintainer import ExportColumn, MaintainerService, MaintainerSpec, build_maintainer_router
from app.db.session import SessionDep
from app.modules.auth.dependencies import CurrentUser, require_permission
from app.modules.auth.models import RefreshToken
from app.modules.auth.security import hash_password
from app.modules.plants.models import Plant
from app.modules.roles.models import Permission, Role, RolePermission
from app.modules.users.models import User, UserRole
from app.modules.users.schemas import TemporaryPasswordOut, UserCreate, UserOut, UserUpdate

ADMIN_PERMISSION = "users.admin"
# Sin caracteres que se confunden al dictarlos o copiarlos (0/O, 1/l/I).
_ALPHABET = "".join(c for c in string.ascii_letters + string.digits if c not in "0O1lI")


def generate_temporary_password(min_length: int) -> str:
    length = max(12, min_length)
    while True:
        candidate = "".join(secrets.choice(_ALPHABET) for _ in range(length))
        if any(c.isdigit() for c in candidate) and any(c.isalpha() for c in candidate):
            return candidate


def has_admin_permission(user: User) -> bool:
    return any(p.code == ADMIN_PERMISSION for r in user.roles if r.is_active for p in r.permissions)


def other_active_admins(session: Any, user_id: int | None) -> int:
    """Usuarios activos con users.admin, sin contar `user_id`."""
    query = (
        select(func.count(func.distinct(User.id)))
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(Permission.code == ADMIN_PERMISSION, User.is_active, Role.is_active)
    )
    if user_id is not None:
        query = query.where(User.id != user_id)
    return int(session.scalar(query) or 0)


def _last_admin_error() -> BusinessRuleError:
    return BusinessRuleError(
        "Debe quedar al menos un usuario activo con permiso para administrar usuarios.",
        code="last_admin",
    )


class UserService(MaintainerService):
    def apply(self, obj: Any, values: dict[str, Any], *, creating: bool) -> None:
        role_ids = values.pop("role_ids", None)
        plant_ids = values.pop("plant_ids", None)
        super().apply(obj, values, creating=creating)
        if role_ids is not None:
            obj.roles = self._load(Role, role_ids, "role_ids", "Rol")
        if plant_ids is not None:
            obj.plants = self._load(Plant, plant_ids, "plant_ids", "Planta")
        if creating:
            temporary = generate_temporary_password(get_settings().auth_password_min_length)
            obj.password_hash = hash_password(temporary)
            obj.must_change_password = True
            # Atributo transitorio: viaja solo en la respuesta del alta.
            obj.temporary_password = temporary

    def validate(self, obj: Any, *, creating: bool) -> None:
        if not creating and not has_admin_permission(obj) and other_active_admins(self.session, obj.id) == 0:
            raise _last_admin_error()

    def before_set_active(self, obj: Any, active: bool) -> None:
        if active:
            return
        if obj.id == self.user.id:
            raise BusinessRuleError("No puede desactivar su propio usuario.", code="self_deactivation")
        if has_admin_permission(obj) and other_active_admins(self.session, obj.id) == 0:
            raise _last_admin_error()
        self._revoke_sessions(obj.id)

    def reset_password(self, user_id: int) -> str:
        user = self.get(user_id)
        temporary = generate_temporary_password(get_settings().auth_password_min_length)
        user.password_hash = hash_password(temporary)
        user.must_change_password = True
        user.locked_at = None
        user.failed_login_count = 0
        self._revoke_sessions(user.id)
        self.session.commit()
        return temporary

    def unlock(self, user_id: int) -> Any:
        user = self.get(user_id)
        if user.locked_at is not None or user.failed_login_count:
            user.locked_at = None
            user.failed_login_count = 0
            self.session.commit()
            self.session.refresh(user)
        return user

    def _load(self, model: Any, ids: Sequence[int], field: str, label: str) -> list[Any]:
        wanted = list(dict.fromkeys(ids))
        found = (
            list(self.session.scalars(select(model).where(model.id.in_(wanted), model.is_active)))
            if wanted
            else []
        )
        missing = sorted(set(wanted) - {o.id for o in found})
        if missing:
            raise BusinessRuleError(
                f"{label} inexistente o inactiva: {', '.join(map(str, missing))}.",
                code="invalid_reference",
                field_errors=[FieldError(field=field, message=f"{label} inválida.", code="invalid")],
            )
        return found

    def _revoke_sessions(self, user_id: int) -> None:
        self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )


spec = MaintainerSpec(
    model=User,
    resource="users",
    label="usuario",
    out_schema=UserOut,
    create_schema=UserCreate,
    update_schema=UserUpdate,
    view_permission=ADMIN_PERMISSION,
    edit_permission=ADMIN_PERMISSION,
    search_fields=("username", "email", "full_name"),
    sort_fields=("username", "full_name", "email", "last_login_at", "created_at"),
    default_sort="username",
    unique_fields={"username": "nombre de usuario", "email": "correo"},
    export_columns=(
        ExportColumn("Usuario", "username", 16),
        ExportColumn("Nombre", "full_name", 28),
        ExportColumn("Correo", "email", 30),
        ExportColumn("Roles", lambda u: ", ".join(r.name for r in u.roles), 30),
        ExportColumn("Plantas", lambda u: ", ".join(p.code for p in u.plants), 20),
        ExportColumn("Activo", "is_active", 8),
        ExportColumn("Bloqueado", "locked", 10),
        ExportColumn("Último ingreso", "last_login_at", 18),
    ),
)

router = build_maintainer_router(spec, UserService)

UserAdmin = Annotated[CurrentUser, Depends(require_permission(ADMIN_PERMISSION))]


@router.post(
    "/{item_id:int}/reset-password",
    response_model=TemporaryPasswordOut,
    summary="Restablecer contraseña: genera una clave temporal y cierra las sesiones del usuario",
)
def reset_password(item_id: int, session: SessionDep, user: UserAdmin) -> TemporaryPasswordOut:
    temporary = UserService(session, user, spec).reset_password(item_id)
    return TemporaryPasswordOut(temporary_password=temporary)


@router.post("/{item_id:int}/unlock", response_model=UserOut, summary="Desbloquear usuario")
def unlock(item_id: int, session: SessionDep, user: UserAdmin) -> Any:
    return UserService(session, user, spec).unlock(item_id)
