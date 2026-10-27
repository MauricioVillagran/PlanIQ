from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.auth.models import RefreshToken
from app.modules.users.models import User
from tests.integration.conftest import TEST_PASSWORD, auth_header, login

pytestmark = pytest.mark.integration

ME = "/api/v1/auth/me"


def test_login_returns_access_token_and_httponly_refresh_cookie(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user("ana", roles=("planning",))
    res = client.post("/api/v1/auth/login", json={"username": "ANA ", "password": TEST_PASSWORD})

    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().jwt_access_ttl_minutes * 60
    assert body["must_change_password"] is False
    cookie = res.headers["set-cookie"]
    assert "planiq_refresh=" in cookie
    assert "HttpOnly" in cookie
    assert "Path=/api/v1/auth" in cookie
    assert "samesite=strict" in cookie.lower()
    assert "refresh" not in body


def test_me_returns_roles_permissions_and_plants(
    client: TestClient, make_user: Callable[..., User], make_plant: Callable[..., object]
) -> None:
    plant = make_plant("VS", "Planta Victoria Sur")
    make_plant("OTRA")
    make_user("ana", roles=("planning",), plants=(plant,))
    token = login(client, "ana")["access_token"]

    me = client.get(ME, headers=auth_header(token)).json()
    assert me["username"] == "ana"
    assert me["roles"] == [{"code": "planning", "name": "Planificación"}]
    assert "plan.publish" in me["permissions"]
    assert "users.admin" not in me["permissions"]
    assert me["all_plants"] is False
    assert [p["code"] for p in me["plants"]] == ["VS"]


def test_admin_sees_all_plants(
    client: TestClient, make_user: Callable[..., User], make_plant: Callable[..., object]
) -> None:
    make_plant("A1")
    make_plant("B1")
    make_user("jefa", roles=("admin",))
    me = client.get(ME, headers=auth_header(login(client, "jefa")["access_token"])).json()
    assert me["all_plants"] is True
    assert {"A1", "B1"} <= {p["code"] for p in me["plants"]}


@pytest.mark.parametrize(("username", "password"), [("ana", "incorrecta"), ("noexiste", TEST_PASSWORD)])
def test_wrong_credentials_give_the_same_generic_error(
    client: TestClient, make_user: Callable[..., User], username: str, password: str
) -> None:
    make_user("ana")
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 401
    assert res.json()["code"] == "invalid_credentials"
    assert res.json()["message"] == "Usuario o contraseña incorrectos."


def test_inactive_user_cannot_login(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user("ana", is_active=False)
    res = client.post("/api/v1/auth/login", json={"username": "ana", "password": TEST_PASSWORD})
    assert res.json()["code"] == "invalid_credentials"


def test_five_failed_attempts_lock_the_account(
    client: TestClient, make_user: Callable[..., User], db_session: Session
) -> None:
    user = make_user("ana")
    codes = [
        client.post("/api/v1/auth/login", json={"username": "ana", "password": "mala"}).json()["code"]
        for _ in range(5)
    ]
    assert codes == ["invalid_credentials"] * 4 + ["account_locked"]

    # Con la cuenta bloqueada, ni la contraseña correcta permite entrar.
    res = client.post("/api/v1/auth/login", json={"username": "ana", "password": TEST_PASSWORD})
    assert res.status_code == 401
    assert res.json()["code"] == "account_locked"
    db_session.refresh(user)
    assert user.locked_at is not None
    assert user.failed_login_count == 5


def test_successful_login_resets_failed_count(
    client: TestClient, make_user: Callable[..., User], db_session: Session
) -> None:
    user = make_user("ana")
    for _ in range(3):
        client.post("/api/v1/auth/login", json={"username": "ana", "password": "mala"})
    login(client, "ana")
    db_session.refresh(user)
    assert user.failed_login_count == 0
    assert user.last_login_at is not None


def test_locked_user_access_token_stops_working(
    client: TestClient, make_user: Callable[..., User], db_session: Session
) -> None:
    user = make_user("ana")
    token = login(client, "ana")["access_token"]
    user.locked_at = datetime.now(UTC)
    db_session.commit()
    res = client.get(ME, headers=auth_header(token))
    assert res.status_code == 401
    assert res.json()["code"] == "account_locked"


def test_login_rate_limit_returns_429(app: FastAPI, make_user: Callable[..., User]) -> None:
    from app.modules.auth.security import RateLimiter

    app.state.login_limiter = RateLimiter("3/minute")
    make_user("ana")
    with TestClient(app) as c:
        statuses = [
            c.post("/api/v1/auth/login", json={"username": "ana", "password": "mala"}).status_code
            for _ in range(4)
        ]
    assert statuses == [401, 401, 401, 429]


def test_first_login_requires_password_change(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user("nuevo", roles=("production",), must_change_password=True)
    first = login(client, "nuevo")
    assert first["must_change_password"] is True

    # /me sí responde, para que el frontend sepa que debe pedir el cambio.
    assert client.get(ME, headers=auth_header(first["access_token"])).json()["must_change_password"] is True

    res = client.post(
        "/api/v1/auth/change-password",
        headers=auth_header(first["access_token"]),
        json={"current_password": TEST_PASSWORD, "new_password": "Otra-clave-segura-2"},
    )
    assert res.status_code == 200
    assert res.json()["must_change_password"] is False
    # La nueva contraseña funciona y la anterior no.
    login(client, "nuevo", "Otra-clave-segura-2")
    old = client.post("/api/v1/auth/login", json={"username": "nuevo", "password": TEST_PASSWORD})
    assert old.status_code == 401


@pytest.mark.parametrize(
    ("current", "new", "code", "field"),
    [
        ("incorrecta", "Otra-clave-segura-2", "invalid_current_password", "current_password"),
        (TEST_PASSWORD, "corta", "password_policy", "new_password"),
        (TEST_PASSWORD, TEST_PASSWORD, "password_policy", "new_password"),
        (TEST_PASSWORD, "usuario-largo", "password_policy", "new_password"),
    ],
)
def test_change_password_validations(
    client: TestClient, make_user: Callable[..., User], current: str, new: str, code: str, field: str
) -> None:
    make_user("usuario-largo")
    token = login(client, "usuario-largo")["access_token"]
    res = client.post(
        "/api/v1/auth/change-password",
        headers=auth_header(token),
        json={"current_password": current, "new_password": new},
    )
    assert res.status_code == 422
    assert res.json()["code"] == code
    assert res.json()["field_errors"][0]["field"] == field


def test_refresh_rotates_token_and_detects_reuse(
    client: TestClient, make_user: Callable[..., User], db_session: Session
) -> None:
    make_user("ana")
    login(client, "ana")
    first_cookie = client.cookies.get("planiq_refresh")
    assert first_cookie

    rotated = client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200
    second_cookie = client.cookies.get("planiq_refresh")
    assert second_cookie and second_cookie != first_cookie
    assert client.get(ME, headers=auth_header(rotated.json()["access_token"])).status_code == 200

    # Reusar el token ya rotado revoca toda la familia, incluido el vigente.
    _use_refresh_cookie(client, first_cookie)
    reuse = client.post("/api/v1/auth/refresh")
    assert reuse.json()["code"] == "refresh_reused"
    _use_refresh_cookie(client, second_cookie)
    assert client.post("/api/v1/auth/refresh").json()["code"] == "refresh_reused"
    active = db_session.scalars(select(RefreshToken).where(RefreshToken.revoked_at.is_(None))).all()
    assert active == []


def test_expired_refresh_is_rejected(
    client: TestClient, make_user: Callable[..., User], db_session: Session
) -> None:
    make_user("ana")
    login(client, "ana")
    for token in db_session.scalars(select(RefreshToken)):
        token.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()
    assert client.post("/api/v1/auth/refresh").json()["code"] == "refresh_expired"


def test_logout_revokes_refresh_and_clears_cookie(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user("ana")
    login(client, "ana")
    cookie = client.cookies.get("planiq_refresh")
    res = client.post("/api/v1/auth/logout")
    assert res.status_code == 204
    assert 'planiq_refresh=""' in res.headers["set-cookie"] or "Max-Age=0" in res.headers["set-cookie"]
    _use_refresh_cookie(client, cookie or "")
    assert client.post("/api/v1/auth/refresh").status_code == 401


@pytest.mark.parametrize(
    ("header", "code"),
    [
        ({}, "not_authenticated"),
        ({"Authorization": "Bearer basura"}, "invalid_token"),
        ({"Authorization": "Basic abc"}, "not_authenticated"),
    ],
)
def test_me_requires_valid_token(client: TestClient, header: dict[str, str], code: str) -> None:
    res = client.get(ME, headers=header)
    assert res.status_code == 401
    assert res.json()["code"] == code


def test_expired_access_token_is_rejected(client: TestClient, make_user: Callable[..., User]) -> None:
    from app.modules.auth.security import create_access_token

    user = make_user("ana")
    token, _ = create_access_token(user.id, get_settings(), now=datetime.now(UTC) - timedelta(hours=1))
    res = client.get(ME, headers=auth_header(token))
    assert res.json()["code"] == "token_expired"


def _use_refresh_cookie(client: TestClient, value: str) -> None:
    """Reemplaza la cookie de sesión del cliente (sin dejar dos cookies con el mismo nombre)."""
    client.cookies.clear()
    client.cookies.set("planiq_refresh", value)
