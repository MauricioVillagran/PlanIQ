"""Mantenedores de administración: usuarios, roles y permisos, turnos y parámetros."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.parameters.values import get_parameter
from app.modules.plants.models import Plant
from app.modules.roles.models import Permission, Role
from app.modules.users.models import User
from tests.integration.conftest import auth_header, login

pytestmark = pytest.mark.integration

Headers = dict[str, str]


@pytest.fixture
def admin(client: TestClient, make_user: Callable[..., User]) -> Headers:
    make_user("jefa", roles=("admin",))
    return auth_header(login(client, "jefa")["access_token"])


def _role_id(session: Session, code: str) -> int:
    return session.scalars(select(Role.id).where(Role.code == code)).one()


def _ok(res: Any, status: int = 200) -> dict[str, Any]:
    assert res.status_code == status, res.text
    data: dict[str, Any] = res.json()
    return data


# --- Usuarios ------------------------------------------------------------------------------


def _create_user(client: TestClient, admin: Headers, session: Session, **overrides: Any) -> dict[str, Any]:
    body = {
        "username": "MPerez",
        "email": "MPerez@Example.com",
        "full_name": "María Pérez",
        "role_ids": [_role_id(session, "production")],
    } | overrides
    return _ok(client.post("/api/v1/users", json=body, headers=admin), 201)


def test_create_user_returns_temporary_password_once(
    client: TestClient, admin: Headers, db_session: Session, make_plant: Callable[..., Plant]
) -> None:
    plant = make_plant("VS")
    user = _create_user(client, admin, db_session, plant_ids=[plant.id])
    assert user["username"] == "mperez"
    assert user["email"] == "mperez@example.com"
    assert user["must_change_password"] is True
    assert [r["code"] for r in user["roles"]] == ["production"]
    assert [p["code"] for p in user["plants"]] == ["VS"]
    temporary = user["temporary_password"]
    assert temporary and len(temporary) >= 12

    detail = _ok(client.get(f"/api/v1/users/{user['id']}", headers=admin))
    assert detail["temporary_password"] is None
    assert "password_hash" not in detail

    session = login(client, "mperez", temporary)
    assert session["must_change_password"] is True


@pytest.mark.parametrize(
    ("overrides", "field", "code"),
    [
        ({"username": "jefa"}, "username", "unique"),
        ({"email": "jefa@example.com"}, "email", "unique"),
        ({"username": "con espacio"}, "username", "string_pattern_mismatch"),
        ({"email": "sin-arroba"}, "email", "string_pattern_mismatch"),
        ({"role_ids": []}, "role_ids", "too_short"),
        ({"role_ids": [999999]}, "role_ids", "invalid"),
    ],
)
def test_create_user_validations(
    client: TestClient, admin: Headers, db_session: Session, overrides: dict[str, Any], field: str, code: str
) -> None:
    body = {
        "username": "nuevo",
        "email": "nuevo@example.com",
        "full_name": "Nuevo",
        "role_ids": [_role_id(db_session, "production")],
    } | overrides
    res = client.post("/api/v1/users", json=body, headers=admin)
    assert res.status_code == 422, res.text
    assert {e["field"]: e["code"] for e in res.json()["field_errors"]}[field] == code


def test_update_roles_and_plants_is_audited(
    client: TestClient, admin: Headers, db_session: Session, make_plant: Callable[..., Plant]
) -> None:
    plant = make_plant("VS")
    user = _create_user(client, admin, db_session)
    updated = _ok(
        client.patch(
            f"/api/v1/users/{user['id']}",
            json={
                "role_ids": [_role_id(db_session, "quality")],
                "plant_ids": [plant.id],
                "row_version": user["row_version"],
            },
            headers=admin,
        )
    )
    assert [r["code"] for r in updated["roles"]] == ["quality"]
    history = _ok(client.get(f"/api/v1/users/{user['id']}/history", headers=admin))
    change = history["items"][0]["changes"]
    assert change["roles"]["added"][0]["code"] == "quality"
    assert change["roles"]["removed"][0]["code"] == "production"
    assert change["plants"]["added"][0]["code"] == "VS"


def test_reset_password_replaces_password_and_closes_sessions(
    client: TestClient, admin: Headers, db_session: Session
) -> None:
    user = _create_user(client, admin, db_session)
    first = user["temporary_password"]
    login(client, "mperez", first)

    reset = _ok(client.post(f"/api/v1/users/{user['id']}/reset-password", headers=admin))
    second = reset["temporary_password"]
    assert second != first
    assert (
        client.post("/api/v1/auth/login", json={"username": "mperez", "password": first}).status_code == 401
    )
    assert login(client, "mperez", second)["must_change_password"] is True


def test_unlock_after_failed_attempts(
    client: TestClient, admin: Headers, db_session: Session, make_user: Callable[..., User]
) -> None:
    make_user("ana")
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"username": "ana", "password": "mala"})
    ana = db_session.scalars(select(User).where(User.username == "ana")).one()
    listed = _ok(client.get("/api/v1/users", params={"q": "ana"}, headers=admin))
    assert listed["items"][0]["locked"] is True

    unlocked = _ok(client.post(f"/api/v1/users/{ana.id}/unlock", headers=admin))
    assert unlocked["locked"] is False
    login(client, "ana")


def test_cannot_deactivate_yourself(client: TestClient, admin: Headers, db_session: Session) -> None:
    me = db_session.scalars(select(User).where(User.username == "jefa")).one()
    res = client.post(f"/api/v1/users/{me.id}/deactivate", headers=admin)
    assert res.status_code == 422
    assert res.json()["code"] == "self_deactivation"


def test_last_admin_is_protected(
    client: TestClient, admin: Headers, db_session: Session, make_user: Callable[..., User]
) -> None:
    other = make_user("otra_admin", roles=("admin",))
    me = db_session.scalars(select(User).where(User.username == "jefa")).one()

    # Con dos administradores, a uno se le puede quitar el rol.
    detail = _ok(client.get(f"/api/v1/users/{other.id}", headers=admin))
    _ok(
        client.patch(
            f"/api/v1/users/{other.id}",
            json={"role_ids": [_role_id(db_session, "planning")], "row_version": detail["row_version"]},
            headers=admin,
        )
    )
    # Ahora "jefa" es la única: no puede quedarse sin administración.
    mine = _ok(client.get(f"/api/v1/users/{me.id}", headers=admin))
    res = client.patch(
        f"/api/v1/users/{me.id}",
        json={"role_ids": [_role_id(db_session, "planning")], "row_version": mine["row_version"]},
        headers=admin,
    )
    assert res.status_code == 422
    assert res.json()["code"] == "last_admin"


def test_deactivated_user_loses_access_immediately(
    client: TestClient, admin: Headers, make_user: Callable[..., User]
) -> None:
    ana = make_user("ana", roles=("planning",))
    token = login(client, "ana")["access_token"]
    _ok(client.post(f"/api/v1/users/{ana.id}/deactivate", headers=admin))
    assert client.get("/api/v1/auth/me", headers=auth_header(token)).status_code == 401
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_users_require_users_admin(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user("ana", roles=("planning",))
    headers = auth_header(login(client, "ana")["access_token"])
    assert client.get("/api/v1/users", headers=headers).status_code == 403


# --- Roles y permisos ----------------------------------------------------------------------


def test_permission_catalog(client: TestClient, admin: Headers) -> None:
    res = client.get("/api/v1/permissions", headers=admin)
    assert res.status_code == 200
    catalog: list[dict[str, Any]] = res.json()
    codes = {p["code"] for p in catalog}
    assert {"users.admin", "plan.publish", "rules.edit", "plants.all"} <= codes
    assert all(p["module"] for p in catalog)


def test_base_roles_listed_with_their_matrix(client: TestClient, admin: Headers) -> None:
    roles = {r["code"]: r for r in _ok(client.get("/api/v1/roles", headers=admin))["items"]}
    assert roles["production"]["permissions"] == ["masters.view", "plan.view", "production.record"]
    assert roles["admin"]["is_system"] is True


def test_create_and_edit_custom_role(client: TestClient, admin: Headers) -> None:
    role = _ok(
        client.post(
            "/api/v1/roles",
            json={"code": "supervisor", "name": "Supervisor de planta", "permissions": ["plan.view"]},
            headers=admin,
        ),
        201,
    )
    assert role["is_system"] is False
    edited = _ok(
        client.patch(
            f"/api/v1/roles/{role['id']}",
            json={"permissions": ["plan.view", "production.record"], "row_version": role["row_version"]},
            headers=admin,
        )
    )
    assert edited["permissions"] == ["plan.view", "production.record"]
    assert _ok(client.post(f"/api/v1/roles/{role['id']}/deactivate", headers=admin))["is_active"] is False


def test_role_with_unknown_permission(client: TestClient, admin: Headers) -> None:
    res = client.post(
        "/api/v1/roles", json={"code": "x_role", "name": "X", "permissions": ["no.existe"]}, headers=admin
    )
    assert res.status_code == 422
    assert res.json()["code"] == "invalid_reference"


def test_base_roles_cannot_be_deactivated(client: TestClient, admin: Headers, db_session: Session) -> None:
    res = client.post(f"/api/v1/roles/{_role_id(db_session, 'planning')}/deactivate", headers=admin)
    assert res.status_code == 422
    assert res.json()["code"] == "system_role"


def test_matrix_edit_cannot_remove_the_last_admin_access(
    client: TestClient, admin: Headers, db_session: Session
) -> None:
    role_id = _role_id(db_session, "admin")
    current = _ok(client.get(f"/api/v1/roles/{role_id}", headers=admin))
    res = client.patch(
        f"/api/v1/roles/{role_id}",
        json={"permissions": ["plan.view"], "row_version": current["row_version"]},
        headers=admin,
    )
    assert res.status_code == 422
    assert res.json()["code"] == "last_admin"


def test_matrix_change_takes_effect_on_next_request(
    client: TestClient, admin: Headers, db_session: Session, make_user: Callable[..., User]
) -> None:
    make_user("ana", roles=("production",))
    token = auth_header(login(client, "ana")["access_token"])
    assert client.get("/api/v1/audit", headers=token).status_code == 403

    role_id = _role_id(db_session, "production")
    current = _ok(client.get(f"/api/v1/roles/{role_id}", headers=admin))
    _ok(
        client.patch(
            f"/api/v1/roles/{role_id}",
            json={
                "permissions": [*current["permissions"], "audit.view"],
                "row_version": current["row_version"],
            },
            headers=admin,
        )
    )
    assert client.get("/api/v1/audit", headers=token).status_code == 200


# --- Turnos --------------------------------------------------------------------------------


def _shift(client: TestClient, admin: Headers, plant_id: int, name: str, start: str, end: str) -> Any:
    return client.post(
        "/api/v1/shifts",
        json={"plant_id": plant_id, "name": name, "start_time": start, "end_time": end},
        headers=admin,
    )


def test_victoria_sur_day_and_night_shifts(
    client: TestClient, admin: Headers, make_plant: Callable[..., Plant]
) -> None:
    plant = make_plant("VS", "Planta Victoria Sur")
    day = _ok(_shift(client, admin, plant.id, "Día", "08:00", "20:00"), 201)
    night = _ok(_shift(client, admin, plant.id, "Noche", "20:00", "08:00"), 201)
    assert day["crosses_midnight"] is False
    assert night["crosses_midnight"] is True
    assert night["duration_minutes"] == 720

    coverage = _ok(client.get("/api/v1/shifts/coverage", params={"plant_id": plant.id}, headers=admin))
    assert coverage == {
        "plant_id": plant.id,
        "full_coverage_required": False,
        "covered": True,
        "gaps": [],
        "covered_minutes": 1440,
    }


def test_overlapping_shift_is_rejected(
    client: TestClient, admin: Headers, make_plant: Callable[..., Plant]
) -> None:
    plant = make_plant("VS")
    _ok(_shift(client, admin, plant.id, "Noche", "20:00", "08:00"), 201)
    res = _shift(client, admin, plant.id, "Madrugada", "06:00", "10:00")
    assert res.status_code == 422
    assert res.json()["code"] == "shift_overlap"
    assert res.json()["details"] == {"overlaps_with": ["Noche"]}


def test_shift_rules(client: TestClient, admin: Headers, make_plant: Callable[..., Plant]) -> None:
    plant, other = make_plant("VS"), make_plant("P2")
    assert _shift(client, admin, plant.id, "Cero", "08:00", "08:00").json()["code"] == "invalid_shift_window"
    _ok(_shift(client, admin, plant.id, "Día", "08:00", "16:00"), 201)
    assert _shift(client, admin, plant.id, "Día", "16:00", "20:00").json()["code"] == "duplicate"
    _ok(_shift(client, admin, other.id, "Día", "08:00", "16:00"), 201)  # mismo nombre, otra planta


def test_reactivating_an_overlapping_shift_is_rejected(
    client: TestClient, admin: Headers, make_plant: Callable[..., Plant]
) -> None:
    plant = make_plant("VS")
    old = _ok(_shift(client, admin, plant.id, "Antiguo", "06:00", "14:00"), 201)
    _ok(client.post(f"/api/v1/shifts/{old['id']}/deactivate", headers=admin))
    _ok(_shift(client, admin, plant.id, "Nuevo", "07:00", "15:00"), 201)
    res = client.post(f"/api/v1/shifts/{old['id']}/activate", headers=admin)
    assert res.json()["code"] == "shift_overlap"


def test_coverage_reports_gaps_and_plant_parameter(
    client: TestClient, admin: Headers, make_plant: Callable[..., Plant]
) -> None:
    plant = make_plant("VS")
    _ok(_shift(client, admin, plant.id, "A", "06:00", "14:00"), 201)
    _ok(_shift(client, admin, plant.id, "B", "14:00", "22:00"), 201)
    _ok(
        client.post(
            "/api/v1/parameters",
            json={"key": "shifts.full_coverage", "plant_id": plant.id, "value_type": "bool", "value": "true"},
            headers=admin,
        ),
        201,
    )
    coverage = _ok(client.get("/api/v1/shifts/coverage", params={"plant_id": plant.id}, headers=admin))
    assert coverage["full_coverage_required"] is True
    assert coverage["covered"] is False
    assert coverage["gaps"] == [{"start": "22:00:00", "end": "06:00:00"}]
    assert coverage["covered_minutes"] == 16 * 60


def test_shifts_respect_plant_access(
    client: TestClient, admin: Headers, make_user: Callable[..., User], make_plant: Callable[..., Plant]
) -> None:
    own, other = make_plant("P1"), make_plant("P2")
    _ok(_shift(client, admin, own.id, "Día", "08:00", "20:00"), 201)
    _ok(_shift(client, admin, other.id, "Día", "08:00", "20:00"), 201)
    make_user("ana", roles=("production",), plants=(own,))
    headers = auth_header(login(client, "ana")["access_token"])

    listed = _ok(client.get("/api/v1/shifts", headers=headers))
    assert {s["plant_id"] for s in listed["items"]} == {own.id}
    assert (
        client.get("/api/v1/shifts/coverage", params={"plant_id": other.id}, headers=headers).status_code
        == 403
    )
    assert _shift(client, headers, own.id, "Noche", "20:00", "08:00").status_code == 403  # sin masters.edit


# --- Parámetros ----------------------------------------------------------------------------


def _param(client: TestClient, headers: Headers, **body: Any) -> Any:
    return client.post("/api/v1/parameters", json=body, headers=headers)


def test_seeded_global_parameter(client: TestClient, admin: Headers, db_session: Session) -> None:
    items = _ok(client.get("/api/v1/parameters", params={"key": "shifts.full_coverage"}, headers=admin))[
        "items"
    ]
    assert [(p["plant_id"], p["value"]) for p in items] == [(None, "false")]
    assert get_parameter(db_session, "shifts.full_coverage") is False


def test_plant_value_overrides_global(
    client: TestClient, admin: Headers, db_session: Session, make_plant: Callable[..., Plant]
) -> None:
    plant = make_plant("VS")
    common = {"key": "harvest.avg_weight_kg.max", "value_type": "decimal", "unit": "kg"}
    _ok(_param(client, admin, **common, value="7,5"), 201)
    created = _ok(_param(client, admin, **common, plant_id=plant.id, value="6.80"), 201)
    assert created["value"] == "6.8"  # normalizado

    assert get_parameter(db_session, "harvest.avg_weight_kg.max", plant.id) == Decimal("6.8")
    assert get_parameter(db_session, "harvest.avg_weight_kg.max", None) == Decimal("7.5")
    assert get_parameter(db_session, "no.definido") is None


def test_parameter_versions_by_validity(
    client: TestClient, admin: Headers, db_session: Session, make_plant: Callable[..., Plant]
) -> None:
    plant = make_plant("VS")
    base = {"key": "refresh.seconds", "value_type": "int", "plant_id": plant.id}
    _ok(_param(client, admin, **base, value="120", valid_to="2026-11-01"), 201)
    _ok(_param(client, admin, **base, value="60", valid_from="2026-11-01"), 201)
    overlap = _param(client, admin, **base, value="30", valid_from="2026-10-15", valid_to="2026-12-01")
    assert overlap.json()["code"] == "validity_overlap"

    assert get_parameter(db_session, "refresh.seconds", plant.id, on=date(2026, 10, 31)) == 120
    assert get_parameter(db_session, "refresh.seconds", plant.id, on=date(2026, 11, 1)) == 60


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"key": "x.int", "value_type": "int", "value": "1.5"}, "invalid_value"),
        ({"key": "x.bool", "value_type": "bool", "value": "quizás"}, "invalid_value"),
        ({"key": "Mayúscula", "value_type": "text", "value": "a"}, "validation_error"),
        (
            {
                "key": "x.dates",
                "value_type": "int",
                "value": "1",
                "valid_from": "2026-02-01",
                "valid_to": "2026-01-01",
            },
            "invalid_validity",
        ),
    ],
)
def test_parameter_validations(client: TestClient, admin: Headers, body: dict[str, Any], code: str) -> None:
    res = _param(client, admin, **body)
    assert res.status_code == 422, res.text
    assert res.json()["code"] == code


def test_parameter_type_must_match_existing_key(client: TestClient, admin: Headers) -> None:
    res = _param(
        client, admin, key="shifts.full_coverage", value_type="int", value="1", valid_from="2030-01-01"
    )
    assert res.json()["code"] == "value_type_mismatch"


def test_global_parameters_require_all_plants(
    client: TestClient, make_user: Callable[..., User], make_plant: Callable[..., Plant], db_session: Session
) -> None:
    plant = make_plant("VS")
    role = Role(code="param_editor", name="Editor de parámetros")
    role.permissions.extend(
        db_session.scalars(select(Permission).where(Permission.code.in_(["masters.view", "parameters.edit"])))
    )
    db_session.add(role)
    db_session.commit()
    make_user("ana", roles=("param_editor",), plants=(plant,))
    headers = auth_header(login(client, "ana")["access_token"])

    denied = _param(client, headers, key="x.global", value_type="int", value="1")
    assert denied.status_code == 403
    assert denied.json()["code"] == "global_parameter_denied"
    _ok(_param(client, headers, key="x.local", value_type="int", value="1", plant_id=plant.id), 201)
