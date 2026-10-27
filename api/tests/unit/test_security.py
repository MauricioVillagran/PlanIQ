from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.errors import AuthenticationError
from app.modules.auth.security import (
    RateLimiter,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    password_policy_errors,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("Una-clave-larga")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "Una-clave-larga") == (True, False)
    assert verify_password(hashed, "otra") == (False, False)


def test_verify_without_hash_always_fails() -> None:
    assert verify_password(None, "lo-que-sea") == (False, False)


def test_access_token_roundtrip() -> None:
    settings = get_settings()
    token, expires_in = create_access_token(42, settings)
    assert expires_in == settings.jwt_access_ttl_minutes * 60
    assert decode_access_token(token, settings) == 42


def test_expired_token_is_rejected() -> None:
    settings = get_settings()
    token, _ = create_access_token(1, settings, now=datetime.now(UTC) - timedelta(hours=2))
    with pytest.raises(AuthenticationError) as exc:
        decode_access_token(token, settings)
    assert exc.value.code == "token_expired"


@pytest.mark.parametrize(
    "token",
    [
        # Firmado con otra clave.
        jwt.encode({"sub": "1", "type": "access", "iat": 0, "exp": 9999999999}, "x" * 32, algorithm="HS256"),
        "no-es-un-jwt",
    ],
)
def test_tampered_tokens_are_rejected(token: str) -> None:
    with pytest.raises(AuthenticationError) as exc:
        decode_access_token(token, get_settings())
    assert exc.value.code == "invalid_token"


def test_wrong_token_type_signed_with_real_secret_is_rejected() -> None:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": "1",
            "type": "refresh",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError):
        decode_access_token(token, settings)


def test_refresh_token_is_random_and_only_hash_is_kept() -> None:
    raw1, hash1 = new_refresh_token()
    raw2, _ = new_refresh_token()
    assert raw1 != raw2
    assert hash1 == hash_refresh_token(raw1)
    assert len(hash1) == 64 and raw1 not in hash1


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("corta", ["Debe tener al menos 10 caracteres."]),
        ("Ana.Perez1", ["No puede ser igual al nombre de usuario."]),
        ("Suficientemente-larga", []),
    ],
)
def test_password_policy(password: str, expected: list[str]) -> None:
    assert password_policy_errors(password, username="ana.perez1", min_length=10) == expected


def test_rate_limiter_sliding_window() -> None:
    limiter = RateLimiter("2/minute")
    assert limiter.hit("1.1.1.1", now=0) is True
    assert limiter.hit("1.1.1.1", now=10) is True
    assert limiter.hit("1.1.1.1", now=20) is False
    assert limiter.hit("2.2.2.2", now=20) is True  # otra IP no se ve afectada
    assert limiter.hit("1.1.1.1", now=60.5) is True  # salió el primer intento de la ventana
