from collections.abc import Callable
from typing import Annotated

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bootstrap import create_initial_admin
from app.core.config import get_settings
from app.modules.auth.dependencies import CurrentUser, CurrentUserDep, ensure_plant_access, require_permission
from app.modules.plants.models import Plant
from app.modules.roles.models import Permission, Role
from app.modules.users.models import User
from tests.integration.conftest import auth_header, login

pytestmark = pytest.mark.integration


@pytest.fixture
def protected_client(app: FastAPI) -> TestClient:
    """Rutas de prueba que usan las dependencias tal como lo harán los módulos reales."""
    router = APIRouter(prefix="/api/v1/test")

    @router.post("/plans/publish")
    def publish(user: Annotated[CurrentUser, Depends(require_permission("plan.publish"))]) -> dict[str, int]:
        return {"user_id": user.id}

    @router.get("/plants/{plant_id}/data")
    def plant_data(plant_id: int, user: CurrentUserDep) -> dict[str, int]:
        ensure_plant_access(user, plant_id)
        return {"plant_id": plant_id}

    app.include_router(router)
    return TestClient(app)


def test_base_roles_and_permission_matrix_are_seeded(db_session: Session) -> None:
    roles = {r.code: r for r in db_session.scalars(select(Role))}
    assert set(roles) >= {"planning", "production", "quality", "admin"}
    assert all(roles[c].is_system for c in ("planning", "production", "quality", "admin"))
    all_codes = set(db_session.scalars(select(Permission.code)))
    assert {p.code for p in roles["admin"].permissions} == all_codes
    assert {p.code for p in roles["production"].permissions} == {
        "masters.view",
        "plan.view",
        "production.record",
    }
    assert "rules.edit" in {p.code for p in roles["quality"].permissions}
    assert "rules.edit" not in {p.code for p in roles["planning"].permissions}


@pytest.mark.parametrize(("role", "status"), [("planning", 200), ("production", 403), ("quality", 403)])
def test_require_permission(
    protected_client: TestClient, make_user: Callable[..., User], role: str, status: int
) -> None:
    make_user("u1", roles=(role,))
    res = protected_client.post(
        "/api/v1/test/plans/publish", headers=auth_header(login(protected_client, "u1")["access_token"])
    )
    assert res.status_code == status
    if status == 403:
        assert res.json()["code"] == "permission_denied"
        assert res.json()["details"] == {"missing_permissions": ["plan.publish"]}


def test_user_with_pending_password_change_is_blocked_from_the_system(
    protected_client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user("u1", roles=("planning",), must_change_password=True)
    token = login(protected_client, "u1")["access_token"]
    res = protected_client.post("/api/v1/test/plans/publish", headers=auth_header(token))
    assert res.status_code == 403
    assert res.json()["code"] == "password_change_required"


def test_plant_access_is_limited_to_assigned_plants(
    protected_client: TestClient, make_user: Callable[..., User], make_plant: Callable[..., Plant]
) -> None:
    own, other = make_plant("P1"), make_plant("P2")
    make_user("u1", roles=("production",), plants=(own,))
    headers = auth_header(login(protected_client, "u1")["access_token"])

    assert protected_client.get(f"/api/v1/test/plants/{own.id}/data", headers=headers).status_code == 200
    denied = protected_client.get(f"/api/v1/test/plants/{other.id}/data", headers=headers)
    assert denied.status_code == 403
    assert denied.json()["code"] == "plant_access_denied"


def test_inactive_plant_is_not_accessible(
    protected_client: TestClient, make_user: Callable[..., User], make_plant: Callable[..., Plant]
) -> None:
    plant = make_plant("P1", is_active=False)
    make_user("u1", roles=("production",), plants=(plant,))
    headers = auth_header(login(protected_client, "u1")["access_token"])
    assert protected_client.get(f"/api/v1/test/plants/{plant.id}/data", headers=headers).status_code == 403


def test_plants_all_permission_grants_every_plant(
    protected_client: TestClient, make_user: Callable[..., User], make_plant: Callable[..., Plant]
) -> None:
    plant = make_plant("P9")
    make_user("jefa", roles=("admin",))
    headers = auth_header(login(protected_client, "jefa")["access_token"])
    assert protected_client.get(f"/api/v1/test/plants/{plant.id}/data", headers=headers).status_code == 200


def test_deactivated_role_stops_granting_permissions(
    protected_client: TestClient, make_user: Callable[..., User], db_session: Session
) -> None:
    make_user("u1", roles=("planning",))
    token = login(protected_client, "u1")["access_token"]
    role = db_session.scalars(select(Role).where(Role.code == "planning")).one()
    role.is_active = False
    db_session.commit()
    assert protected_client.post("/api/v1/test/plans/publish", headers=auth_header(token)).status_code == 403


def test_initial_admin_is_created_once_and_must_change_password(db_session: Session) -> None:
    if db_session.scalar(select(User).limit(1)) is not None:
        pytest.skip("La base de test ya tiene usuarios")
    settings = get_settings().model_copy(
        update={
            "initial_admin_username": "Admin",
            "initial_admin_email": "Admin@Example.com",
            "initial_admin_password": SecretStr("Temporal-123456"),
        }
    )
    admin = create_initial_admin(db_session, settings)
    assert admin is not None
    assert admin.username == "admin"
    assert admin.email == "admin@example.com"
    assert admin.must_change_password is True
    assert [r.code for r in admin.roles] == ["admin"]
    assert create_initial_admin(db_session, settings) is None
