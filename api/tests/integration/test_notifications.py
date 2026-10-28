"""Avisos internos: al publicar o modificar el plan, la campana de los demás roles de la planta."""

from collections.abc import Callable
from datetime import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.farms.models import Cage, FarmCenter, HoldingCage
from app.modules.plants.models import Plant
from app.modules.shifts.models import Shift
from app.modules.users.models import User
from tests.integration.conftest import auth_header, login

pytestmark = pytest.mark.integration

DAY = "2026-11-02"


@pytest.fixture
def published(
    db_session: Session,
    make_plant: Callable[..., Plant],
    make_user: Callable[..., User],
    client: TestClient,
) -> dict[str, Any]:
    plant = make_plant("PN")
    other_plant = make_plant("PX")
    center = FarmCenter(code="CN", name="Centro Norte")
    db_session.add(center)
    db_session.flush()
    cage = Cage(farm_center_id=center.id, code="N1")
    holding = HoldingCage(plant_id=plant.id, code="A1", capacity_fish=50_000)
    shift = Shift(
        plant_id=plant.id, name="Día", start_time=time(7), end_time=time(19), crosses_midnight=False
    )
    db_session.add_all([cage, holding, shift])
    db_session.commit()

    make_user("planificadora", roles=("planning",), plants=(plant,))
    make_user("produccion", roles=("production",), plants=(plant,))
    make_user("calidad", roles=("quality",), plants=(plant,))
    make_user("ajeno", roles=("production",), plants=(other_plant,))
    make_user("inactivo", roles=("production",), plants=(plant,), is_active=False)

    token = login(client, "planificadora")["access_token"]
    plan = client.post(
        f"/api/v1/plants/{plant.id}/daily-plans/{DAY}", headers=auth_header(token), json={}
    ).json()
    plan_id = plan["plan"]["id"]
    client.post(
        f"/api/v1/daily-plans/{plan_id}/harvest-entries",
        headers=auth_header(token),
        json={
            "cage_id": cage.id,
            "holding_cage_id": holding.id,
            "shift_id": shift.id,
            "fish_count": 10_000,
            "avg_weight_kg": "4.5",
        },
    )
    detail = client.get(f"/api/v1/daily-plans/{plan_id}", headers=auth_header(token)).json()
    res = client.post(
        f"/api/v1/daily-plans/{plan_id}/publish",
        headers=auth_header(token),
        json={"row_version": detail["plan"]["row_version"]},
    )
    assert res.status_code == 200, res.text
    return {"plant": plant, "plan": res.json(), "planner_token": token}


def _summary(client: TestClient, token: str) -> dict[str, Any]:
    body: dict[str, Any] = client.get("/api/v1/notifications/summary", headers=auth_header(token)).json()
    return body


def test_publishing_notifies_other_roles_of_the_plant_except_the_author(
    client: TestClient, published: dict[str, Any]
) -> None:
    production = login(client, "produccion")["access_token"]
    items = client.get("/api/v1/notifications", headers=auth_header(production)).json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Plan del 02-11-2026 publicado"
    assert items[0]["body"] == "Por Planificadora"
    assert items[0]["link"] == f"/plan?plant={published['plant'].id}&date={DAY}"

    assert _summary(client, login(client, "calidad")["access_token"])["unread"] == 1
    assert _summary(client, published["planner_token"])["unread"] == 0
    assert _summary(client, login(client, "ajeno")["access_token"])["unread"] == 0


def test_changes_notify_with_version_and_reason(client: TestClient, published: dict[str, Any]) -> None:
    plan = published["plan"]
    entry = plan["entries"][0]
    res = client.post(
        f"/api/v1/daily-plans/{plan['plan']['id']}/changes",
        headers=auth_header(published["planner_token"]),
        json={
            "row_version": plan["plan"]["row_version"],
            "reason": "Ajuste por mortalidad",
            "update": [{"id": entry["id"], "row_version": entry["row_version"], "fish_count": 9_000}],
        },
    )
    assert res.status_code == 200, res.text
    production = login(client, "produccion")["access_token"]
    latest = client.get("/api/v1/notifications", headers=auth_header(production)).json()["items"][0]
    assert latest["title"] == "Plan del 02-11-2026 modificado (versión 2)"
    assert latest["body"] == "Por Planificadora · Ajuste por mortalidad"


def test_mark_one_and_all_as_read(client: TestClient, published: dict[str, Any]) -> None:
    token = login(client, "produccion")["access_token"]
    summary = _summary(client, token)
    assert summary["unread"] == 1
    assert summary["poll_seconds"] == 60

    notification = client.get("/api/v1/notifications", headers=auth_header(token)).json()["items"][0]
    read = client.post(f"/api/v1/notifications/{notification['id']}/read", headers=auth_header(token))
    assert read.status_code == 200
    assert read.json()["read_at"] is not None
    assert _summary(client, token)["unread"] == 0

    calidad = login(client, "calidad")["access_token"]
    # Un aviso ajeno no se puede marcar.
    assert (
        client.post(
            f"/api/v1/notifications/{notification['id']}/read", headers=auth_header(calidad)
        ).status_code
        == 404
    )
    assert client.post("/api/v1/notifications/read-all", headers=auth_header(calidad)).json() == {
        "updated": 1
    }
    assert _summary(client, calidad)["unread"] == 0
    unread = client.get(
        "/api/v1/notifications", headers=auth_header(calidad), params={"unread_only": True}
    ).json()
    assert unread["total"] == 0
