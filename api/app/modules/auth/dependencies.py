"""Usuario actual, permisos granulares y acceso por planta, como dependencias de FastAPI."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.db.session import SessionDep
from app.modules.auth.security import decode_access_token
from app.modules.users.models import User

ALL_PLANTS_PERMISSION = "plants.all"

_bearer = HTTPBearer(auto_error=False, description="Token de acceso obtenido en /auth/login")


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    full_name: str
    email: str
    must_change_password: bool
    role_codes: frozenset[str]
    permissions: frozenset[str]
    # None = acceso a todas las plantas (permiso plants.all).
    plant_ids: frozenset[int] | None

    def has_permission(self, code: str) -> bool:
        return code in self.permissions

    def can_access_plant(self, plant_id: int) -> bool:
        return self.plant_ids is None or plant_id in self.plant_ids


def is_locked(user: User, settings: Settings, now: datetime | None = None) -> bool:
    if user.locked_at is None:
        return False
    if settings.auth_auto_unlock_minutes == 0:
        return True
    unlock_at = user.locked_at + timedelta(minutes=settings.auth_auto_unlock_minutes)
    return (now or datetime.now(UTC)) < unlock_at


def build_current_user(user: User) -> CurrentUser:
    active_roles = [r for r in user.roles if r.is_active]
    permissions = frozenset(p.code for r in active_roles for p in r.permissions)
    plant_ids = (
        None if ALL_PLANTS_PERMISSION in permissions else frozenset(p.id for p in user.plants if p.is_active)
    )
    return CurrentUser(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        must_change_password=user.must_change_password,
        role_codes=frozenset(r.code for r in active_roles),
        permissions=permissions,
        plant_ids=plant_ids,
    )


def load_current_user(session: Session, user_id: int, settings: Settings) -> CurrentUser:
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("La cuenta no está activa.", code="account_inactive")
    if is_locked(user, settings):
        raise AuthenticationError("La cuenta está bloqueada.", code="account_locked")
    return build_current_user(user)


def get_current_user_allow_password_change(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    """Usuario autenticado aunque deba cambiar su contraseña.

    Solo para /auth/me, logout y cambio de contraseña; el resto usa `get_current_user`.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError()
    user_id = decode_access_token(credentials.credentials, settings)
    return load_current_user(session, user_id, settings)


def get_current_user(
    user: Annotated[CurrentUser, Depends(get_current_user_allow_password_change)],
) -> CurrentUser:
    """Usuario autenticado y habilitado: si debe cambiar su contraseña, no puede usar el resto del sistema."""
    if user.must_change_password:
        raise PermissionDeniedError(
            "Debe cambiar su contraseña antes de continuar.", code="password_change_required"
        )
    return user


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_permission(*codes: str) -> Callable[[CurrentUser], CurrentUser]:
    """Dependencia que exige todos los permisos indicados: `Depends(require_permission("plan.publish"))`."""

    def dependency(user: CurrentUserDep) -> CurrentUser:
        missing = [c for c in codes if not user.has_permission(c)]
        if missing:
            raise PermissionDeniedError(details={"missing_permissions": missing})
        return user

    return dependency


def ensure_plant_access(user: CurrentUser, plant_id: int) -> None:
    """Toda consulta operacional valida la planta contra las plantas del usuario."""
    if not user.can_access_plant(plant_id):
        raise PermissionDeniedError("No tiene acceso a esta planta.", code="plant_access_denied")
