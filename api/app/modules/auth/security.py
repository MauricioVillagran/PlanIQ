"""Primitivas de seguridad: contraseñas (Argon2), tokens de acceso (JWT) y de refresco, límite de intentos."""

import hashlib
import secrets
import threading
import time
from collections import deque
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings
from app.core.errors import AuthenticationError

_hasher = PasswordHasher()
# Se verifica contra este hash cuando el usuario no existe, para no revelar por tiempo de respuesta
# qué nombres de usuario son válidos.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"  # noqa: S105 (no es una clave)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> tuple[bool, bool]:
    """Devuelve (coincide, requiere_rehash). Con `password_hash=None` gasta el mismo tiempo y falla."""
    try:
        _hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False, False
    if password_hash is None:
        return False, False
    return True, _hasher.check_needs_rehash(password_hash)


def password_policy_errors(password: str, *, username: str, min_length: int) -> list[str]:
    """Reglas mínimas de la política de contraseñas (configurable por parámetro)."""
    errors: list[str] = []
    if len(password) < min_length:
        errors.append(f"Debe tener al menos {min_length} caracteres.")
    if password.strip().lower() == username.strip().lower():
        errors.append("No puede ser igual al nombre de usuario.")
    return errors


def create_access_token(user_id: int, settings: Settings, now: datetime | None = None) -> tuple[str, int]:
    """Devuelve el JWT y su duración en segundos."""
    issued = now or datetime.now(UTC)
    ttl = timedelta(minutes=settings.jwt_access_ttl_minutes)
    claims = {
        "sub": str(user_id),
        "type": ACCESS_TOKEN_TYPE,
        "iat": issued,
        "exp": issued + ttl,
    }
    token = jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=JWT_ALGORITHM)
    return token, int(ttl.total_seconds())


def decode_access_token(token: str, settings: Settings) -> int:
    """Valida firma, expiración y tipo. Devuelve el id de usuario."""
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("La sesión expiró.", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Token inválido.", code="invalid_token") from exc
    if claims.get("type") != ACCESS_TOKEN_TYPE or not str(claims["sub"]).isdigit():
        raise AuthenticationError("Token inválido.", code="invalid_token")
    return int(claims["sub"])


def new_refresh_token() -> tuple[str, str]:
    """Token de refresco aleatorio y su hash (solo el hash se guarda en la base)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


_PERIODS = {"second": 1.0, "minute": 60.0, "hour": 3600.0}


class RateLimiter:
    """Ventana deslizante en memoria, por clave (IP).

    Basta con una réplica de la API; con varias, cada una cuenta por separado y el límite efectivo
    se multiplica. Si se escala horizontalmente, mover este conteo a SQL Server.
    """

    def __init__(self, spec: str) -> None:
        count, period = spec.split("/")
        self.limit = int(count)
        self.window = _PERIODS[period]
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, now: float | None = None) -> bool:
        """Registra un intento. Devuelve False si la clave superó el límite."""
        current = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and current - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(current)
            return True
