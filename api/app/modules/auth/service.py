"""Casos de uso de autenticación: ingreso, refresco, cierre de sesión y cambio de contraseña."""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AuthenticationError, BusinessRuleError, FieldError
from app.modules.auth.dependencies import is_locked
from app.modules.auth.models import RefreshToken
from app.modules.auth.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    password_policy_errors,
    verify_password,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS = "Usuario o contraseña incorrectos."


@dataclass(frozen=True)
class ClientInfo:
    user_agent: str | None
    ip_address: str | None


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    expires_in: int
    refresh_token: str
    must_change_password: bool


def normalize_username(username: str) -> str:
    return username.strip().lower()


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def login(self, username: str, password: str, client: ClientInfo) -> SessionTokens:
        now = datetime.now(UTC)
        user = self.session.scalar(select(User).where(User.username == normalize_username(username)))

        if user is not None and user.is_active and is_locked(user, self.settings, now):
            raise AuthenticationError(self._locked_message(), code="account_locked")

        matches, needs_rehash = verify_password(user.password_hash if user else None, password)
        if user is None or not user.is_active:
            raise AuthenticationError(INVALID_CREDENTIALS, code="invalid_credentials")

        if not matches:
            self._register_failure(user, now)
            self.session.commit()
            logger.warning("Ingreso fallido", extra={"user_id": user.id, "failed": user.failed_login_count})
            if user.locked_at is not None:
                raise AuthenticationError(self._locked_message(), code="account_locked")
            raise AuthenticationError(INVALID_CREDENTIALS, code="invalid_credentials")

        user.failed_login_count = 0
        user.locked_at = None
        user.last_login_at = now
        if needs_rehash:
            user.password_hash = hash_password(password)
        tokens = self._issue(user, client, family_id=str(uuid.uuid4()), now=now)
        self.session.commit()
        logger.info("Ingreso correcto", extra={"user_id": user.id})
        return tokens

    def refresh(self, raw_token: str | None, client: ClientInfo) -> SessionTokens:
        now = datetime.now(UTC)
        if not raw_token:
            raise AuthenticationError(code="refresh_missing")
        token = self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
        )
        if token is None:
            raise AuthenticationError("La sesión no es válida.", code="refresh_invalid")
        if token.revoked_at is not None:
            # Un token ya rotado se volvió a usar: posible robo. Se cierra toda la familia.
            self._revoke_family(token.family_id, now)
            self.session.commit()
            logger.warning("Reutilización de refresh token", extra={"user_id": token.user_id})
            raise AuthenticationError("La sesión no es válida.", code="refresh_reused")
        if token.expires_at <= now:
            raise AuthenticationError("La sesión expiró.", code="refresh_expired")

        user = self.session.get(User, token.user_id)
        if user is None or not user.is_active or is_locked(user, self.settings, now):
            self._revoke_family(token.family_id, now)
            self.session.commit()
            raise AuthenticationError("La cuenta no está habilitada.", code="account_inactive")

        token.revoked_at = now
        tokens = self._issue(user, client, family_id=token.family_id, now=now)
        self.session.commit()
        return tokens

    def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        token = self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
        )
        if token is not None:
            self._revoke_family(token.family_id, datetime.now(UTC))
            self.session.commit()

    def change_password(
        self, user_id: int, current_password: str, new_password: str, client: ClientInfo
    ) -> SessionTokens:
        now = datetime.now(UTC)
        user = self.session.get(User, user_id)
        if user is None:
            raise AuthenticationError()
        matches, _ = verify_password(user.password_hash, current_password)
        if not matches:
            raise BusinessRuleError(
                "La contraseña actual no es correcta.",
                code="invalid_current_password",
                field_errors=[
                    FieldError(field="current_password", message="Contraseña incorrecta.", code="invalid")
                ],
            )
        errors = password_policy_errors(
            new_password, username=user.username, min_length=self.settings.auth_password_min_length
        )
        if verify_password(user.password_hash, new_password)[0]:
            errors.append("Debe ser distinta de la contraseña actual.")
        if errors:
            raise BusinessRuleError(
                "La nueva contraseña no cumple la política.",
                code="password_policy",
                field_errors=[FieldError(field="new_password", message=m, code="policy") for m in errors],
            )

        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        user.password_changed_at = now
        user.updated_by = user.id
        # Cierra las demás sesiones abiertas y entrega una nueva.
        self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
            .execution_options(synchronize_session=False)
        )
        tokens = self._issue(user, client, family_id=str(uuid.uuid4()), now=now)
        self.session.commit()
        logger.info("Contraseña cambiada", extra={"user_id": user.id})
        return tokens

    def _register_failure(self, user: User, now: datetime) -> None:
        user.failed_login_count += 1
        if user.failed_login_count >= self.settings.auth_max_failed_attempts:
            user.locked_at = now

    def _locked_message(self) -> str:
        if self.settings.auth_auto_unlock_minutes:
            return (
                "La cuenta está bloqueada por intentos fallidos. "
                f"Intente en {self.settings.auth_auto_unlock_minutes} minutos o contacte al administrador."
            )
        return "La cuenta está bloqueada por intentos fallidos. Contacte al administrador."

    def _revoke_family(self, family_id: str, now: datetime) -> None:
        self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
            .execution_options(synchronize_session=False)
        )

    def _issue(self, user: User, client: ClientInfo, *, family_id: str, now: datetime) -> SessionTokens:
        access, expires_in = create_access_token(user.id, self.settings, now)
        raw, token_hash = new_refresh_token()
        self.session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=token_hash,
                family_id=family_id,
                expires_at=now + timedelta(hours=self.settings.jwt_refresh_ttl_hours),
                user_agent=(client.user_agent or "")[:400] or None,
                ip_address=client.ip_address,
            )
        )
        return SessionTokens(
            access_token=access,
            expires_in=expires_in,
            refresh_token=raw,
            must_change_password=user.must_change_password,
        )


def count_users(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(User)) or 0)
