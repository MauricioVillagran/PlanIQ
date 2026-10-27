from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.listener import set_actor
from app.modules.audit.models import AuditLog
from app.modules.jobs import repository as jobs
from app.modules.plants.models import Plant
from app.modules.roles.models import Permission, Role
from app.modules.users.models import User
from tests.integration.conftest import TEST_PASSWORD, auth_header, login

pytestmark = pytest.mark.integration


def _entries(session: Session, entity: str, entity_id: int) -> list[AuditLog]:
    session.expire_all()
    return list(
        session.scalars(
            select(AuditLog)
            .where(AuditLog.entity == entity, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.id)
        )
    )


@pytest.fixture
def actor(make_user: Callable[..., User], db_session: Session) -> User:
    user = make_user("auditor", roles=("admin",))
    set_actor(db_session, user.id)
    return user


def test_create_records_snapshot_and_fills_created_by(db_session: Session, actor: User) -> None:
    plant = Plant(code="VS", name="Planta Victoria Sur", plant_type="own", location="Puerto Montt")
    db_session.add(plant)
    db_session.commit()

    assert plant.created_by == actor.id
    (entry,) = _entries(db_session, "master.plants", plant.id)
    assert entry.action == "create"
    assert entry.user_id == actor.id
    assert entry.plant_id == plant.id
    assert entry.changes["code"] == {"new": "VS"}
    assert entry.changes["name"] == {"new": "Planta Victoria Sur"}
    assert "row_version" not in entry.changes
    assert "created_at" not in entry.changes


def test_update_records_field_differences_and_fills_updated_by(db_session: Session, actor: User) -> None:
    plant = Plant(code="VS", name="Planta VS", plant_type="own")
    db_session.add(plant)
    db_session.commit()

    plant.name = "Planta Victoria Sur"
    plant.location = "Calbuco"
    db_session.commit()

    assert plant.updated_by == actor.id
    entry = _entries(db_session, "master.plants", plant.id)[-1]
    assert entry.action == "update"
    assert entry.changes == {
        "name": {"old": "Planta VS", "new": "Planta Victoria Sur"},
        "location": {"old": None, "new": "Calbuco"},
    }


def test_deactivate_and_activate_are_named_actions(db_session: Session, actor: User) -> None:
    plant = Plant(code="VS", name="Planta VS", plant_type="own")
    db_session.add(plant)
    db_session.commit()

    plant.is_active = False
    db_session.commit()
    plant.is_active = True
    db_session.commit()

    actions = [e.action for e in _entries(db_session, "master.plants", plant.id)]
    assert actions == ["create", "deactivate", "activate"]


def test_no_changes_no_entry(db_session: Session, actor: User) -> None:
    plant = Plant(code="VS", name="Planta VS", plant_type="own")
    db_session.add(plant)
    db_session.commit()
    plant.name = "Planta VS"  # mismo valor
    db_session.commit()
    assert len(_entries(db_session, "master.plants", plant.id)) == 1


def test_delete_records_last_values(db_session: Session, actor: User) -> None:
    plant = Plant(code="TMP", name="Temporal", plant_type="contract")
    db_session.add(plant)
    db_session.commit()
    plant_id = plant.id
    db_session.delete(plant)
    db_session.commit()

    entry = _entries(db_session, "master.plants", plant_id)[-1]
    assert entry.action == "delete"
    assert entry.changes["code"] == {"new": "TMP"}


def test_relationship_changes_are_recorded_on_parent(
    db_session: Session, actor: User, make_user: Callable[..., User]
) -> None:
    user = make_user("ana", roles=("planning",))
    quality = db_session.scalars(select(Role).where(Role.code == "quality")).one()
    planning = db_session.scalars(select(Role).where(Role.code == "planning")).one()

    user.roles.remove(planning)
    user.roles.append(quality)
    db_session.commit()

    entry = _entries(db_session, "core.users", user.id)[-1]
    assert entry.action == "update"
    assert entry.changes["roles"]["added"] == [{"id": quality.id, "code": "quality"}]
    assert entry.changes["roles"]["removed"] == [{"id": planning.id, "code": "planning"}]


def test_password_hash_is_masked(db_session: Session, actor: User, make_user: Callable[..., User]) -> None:
    user = make_user("ana")
    create = _entries(db_session, "core.users", user.id)[0]
    assert create.changes["password_hash"] == {"new": "***"}

    user.password_hash = "otro-hash"
    db_session.commit()
    update = _entries(db_session, "core.users", user.id)[-1]
    assert update.changes["password_hash"] == {"old": "***", "new": "***"}


def test_excluded_models_and_fields_are_not_audited(
    db_session: Session, actor: User, make_user: Callable[..., User]
) -> None:
    job = jobs.enqueue(db_session, "system.noop")
    db_session.commit()
    assert _entries(db_session, "integration.jobs", job.id) == []

    user = make_user("ana")
    before = len(_entries(db_session, "core.users", user.id))
    user.failed_login_count = 2
    db_session.commit()
    assert len(_entries(db_session, "core.users", user.id)) == before


def test_system_writes_have_no_user(db_session: Session) -> None:
    set_actor(db_session, None)
    plant = Plant(code="SYS", name="Planta sistema", plant_type="own")
    db_session.add(plant)
    db_session.commit()
    (entry,) = _entries(db_session, "master.plants", plant.id)
    assert entry.user_id is None
    assert plant.created_by is None


def test_api_writes_are_attributed_to_the_user_with_request_id(
    client: TestClient, make_user: Callable[..., User], db_session: Session
) -> None:
    user = make_user("nuevo", must_change_password=True)
    token = login(client, "nuevo")["access_token"]
    res = client.post(
        "/api/v1/auth/change-password",
        headers=auth_header(token) | {"X-Request-ID": "req-cambio-clave"},
        json={"current_password": TEST_PASSWORD, "new_password": "Clave-nueva-segura-9"},
    )
    assert res.status_code == 200

    entry = _entries(db_session, "core.users", user.id)[-1]
    assert entry.user_id == user.id
    assert entry.request_id == "req-cambio-clave"
    assert entry.changes["must_change_password"] == {"old": True, "new": False}
    assert entry.changes["password_hash"] == {"old": "***", "new": "***"}
    assert "last_login_at" not in entry.changes


def test_account_lock_is_audited_as_system_action(
    client: TestClient, make_user: Callable[..., User], db_session: Session
) -> None:
    user = make_user("ana")
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"username": "ana", "password": "mala"})
    entry = _entries(db_session, "core.users", user.id)[-1]
    assert entry.user_id is None
    assert entry.changes["locked_at"]["old"] is None
    assert entry.changes["locked_at"]["new"] is not None


# --- Endpoint /audit -------------------------------------------------------------------


def _audit(client: TestClient, token: str, **params: Any) -> Any:
    return client.get("/api/v1/audit", headers=auth_header(token), params=params)


def test_audit_endpoint_requires_audit_view(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user("ana", roles=("planning",))
    res = _audit(client, login(client, "ana")["access_token"])
    assert res.status_code == 403


def test_audit_endpoint_filters_and_paginates(
    client: TestClient, make_user: Callable[..., User], db_session: Session
) -> None:
    admin = make_user("jefa", roles=("admin",))
    set_actor(db_session, admin.id)
    plant = Plant(code="VS", name="Planta VS", plant_type="own")
    db_session.add(plant)
    db_session.commit()
    for name in ("Uno", "Dos", "Tres"):
        plant.name = name
        db_session.commit()

    token = login(client, "jefa")["access_token"]
    body = _audit(client, token, entity="master.plants", entity_id=plant.id, page_size=2).json()
    assert body["total"] == 4
    assert body["page_size"] == 2
    first = body["items"][0]
    assert first["action"] == "update"
    assert first["changes"]["name"] == {"old": "Dos", "new": "Tres"}
    assert first["username"] == "jefa"

    creates = _audit(client, token, entity="master.plants", entity_id=plant.id, action="create").json()
    assert creates["total"] == 1


def test_audit_endpoint_rejects_dates_without_timezone(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user("jefa", roles=("admin",))
    res = _audit(client, login(client, "jefa")["access_token"], date_from="2026-10-01T00:00:00")
    assert res.status_code == 422


def test_audit_entries_of_other_plants_are_hidden(
    client: TestClient,
    make_user: Callable[..., User],
    make_plant: Callable[..., Plant],
    db_session: Session,
) -> None:
    own, other = make_plant("P1"), make_plant("P2")
    viewer = make_user("auditora", roles=("production",), plants=(own,))
    # Rol de prueba con audit.view pero sin plants.all.
    role = Role(code="auditor_test", name="Auditor de prueba")
    role.permissions.append(
        db_session.scalars(select(Permission).where(Permission.code == "audit.view")).one()
    )
    viewer.roles.append(role)
    db_session.commit()

    token = login(client, "auditora")["access_token"]
    items = _audit(client, token, entity="master.plants", page_size=200).json()["items"]
    plant_ids = {e["plant_id"] for e in items}
    assert own.id in plant_ids
    assert other.id not in plant_ids
