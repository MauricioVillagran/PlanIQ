"""Maestros de cultivo: centros, jaulas y jaulas de acopio (ADR 0005, decisión 6)."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.modules.plants.models import Plant
from app.modules.users.models import User
from tests.integration.conftest import auth_header, login

pytestmark = pytest.mark.integration

Headers = dict[str, str]


@pytest.fixture
def planner(client: TestClient, make_user: Callable[..., User], make_plant: Callable[..., Plant]) -> Headers:
    make_user("plani", roles=("planning",), plants=(make_plant("VS"),))
    return auth_header(login(client, "plani")["access_token"])


def _ok(res: Any, status: int = 200) -> dict[str, Any]:
    assert res.status_code == status, res.text
    data: dict[str, Any] = res.json()
    return data


def _center(client: TestClient, headers: Headers, code: str = "CH-101", **extra: Any) -> dict[str, Any]:
    body = {"code": code, "name": f"Centro {code}"} | extra
    return _ok(client.post("/api/v1/farm-centers", json=body, headers=headers), 201)


def test_planning_maintains_farm_masters_with_farms_edit(client: TestClient, planner: Headers) -> None:
    center = _center(client, planner, zone="Barrio 3A")
    assert center["zone"] == "Barrio 3A"
    cage = _ok(
        client.post("/api/v1/cages", json={"farm_center_id": center["id"], "code": "J-104"}, headers=planner),
        201,
    )
    assert (cage["farm_center_code"], cage["farm_center_name"]) == ("CH-101", "Centro CH-101")


def test_roles_without_farms_edit_only_view(
    client: TestClient, make_user: Callable[..., User], planner: Headers
) -> None:
    _center(client, planner)
    make_user("prod", roles=("production",))
    headers = auth_header(login(client, "prod")["access_token"])
    assert client.get("/api/v1/farm-centers", headers=headers).status_code == 200
    denied = client.post("/api/v1/farm-centers", json={"code": "X", "name": "X"}, headers=headers)
    assert denied.status_code == 403
    assert denied.json()["details"] == {"missing_permissions": ["farms.edit"]}


def test_cage_code_is_unique_within_its_center(client: TestClient, planner: Headers) -> None:
    a, b = _center(client, planner, "C-A"), _center(client, planner, "C-B")
    _ok(client.post("/api/v1/cages", json={"farm_center_id": a["id"], "code": "J-1"}, headers=planner), 201)
    dup = client.post("/api/v1/cages", json={"farm_center_id": a["id"], "code": "J-1"}, headers=planner)
    assert dup.status_code == 422
    assert dup.json()["field_errors"][0] == {
        "field": "code",
        "message": "Ya existe una jaula con ese código en el centro.",
        "code": "unique",
    }
    # El mismo código en otro centro es válido.
    _ok(client.post("/api/v1/cages", json={"farm_center_id": b["id"], "code": "J-1"}, headers=planner), 201)


def test_cage_requires_an_active_center(client: TestClient, planner: Headers) -> None:
    center = _center(client, planner)
    _ok(client.post(f"/api/v1/farm-centers/{center['id']}/deactivate", headers=planner))
    res = client.post("/api/v1/cages", json={"farm_center_id": center["id"], "code": "J-1"}, headers=planner)
    assert res.status_code == 422
    assert res.json()["code"] == "invalid_reference"


def test_cages_filter_by_center(client: TestClient, planner: Headers) -> None:
    a, b = _center(client, planner, "C-A"), _center(client, planner, "C-B")
    for center, code in ((a, "J-1"), (a, "J-2"), (b, "J-9")):
        _ok(
            client.post(
                "/api/v1/cages", json={"farm_center_id": center["id"], "code": code}, headers=planner
            ),
            201,
        )
    listed = _ok(client.get("/api/v1/cages", params={"farm_center_id": a["id"]}, headers=planner))
    assert [c["code"] for c in listed["items"]] == ["J-1", "J-2"]


def test_holding_cages_belong_to_a_plant(
    client: TestClient, planner: Headers, make_plant: Callable[..., Plant]
) -> None:
    listed_plants = _ok(client.get("/api/v1/plants", headers=planner))["items"]
    plant_id = listed_plants[0]["id"]
    created = _ok(
        client.post(
            "/api/v1/holding-cages",
            json={"plant_id": plant_id, "code": "A-1", "capacity_fish": 12000},
            headers=planner,
        ),
        201,
    )
    assert created["capacity_fish"] == 12000

    dup = client.post(
        "/api/v1/holding-cages",
        json={"plant_id": plant_id, "code": "A-1", "capacity_fish": 5000},
        headers=planner,
    )
    assert dup.json()["code"] == "duplicate"

    zero = client.post(
        "/api/v1/holding-cages",
        json={"plant_id": plant_id, "code": "A-2", "capacity_fish": 0},
        headers=planner,
    )
    assert zero.status_code == 422
    assert zero.json()["field_errors"][0]["field"] == "capacity_fish"

    # Sin acceso a otra planta: no puede crear ni ver sus acopios.
    other = make_plant("P2")
    denied = client.post(
        "/api/v1/holding-cages",
        json={"plant_id": other.id, "code": "A-1", "capacity_fish": 100},
        headers=planner,
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "plant_access_denied"


def test_capacity_update_and_history(client: TestClient, planner: Headers) -> None:
    plant_id = _ok(client.get("/api/v1/plants", headers=planner))["items"][0]["id"]
    acopio = _ok(
        client.post(
            "/api/v1/holding-cages",
            json={"plant_id": plant_id, "code": "A-1", "capacity_fish": 12000},
            headers=planner,
        ),
        201,
    )
    _ok(
        client.patch(
            f"/api/v1/holding-cages/{acopio['id']}",
            json={"capacity_fish": 15000, "row_version": acopio["row_version"]},
            headers=planner,
        )
    )
    history = _ok(client.get(f"/api/v1/holding-cages/{acopio['id']}/history", headers=planner))
    assert history["items"][0]["changes"]["capacity_fish"] == {"old": 12000, "new": 15000}


def test_farms_export(client: TestClient, planner: Headers) -> None:
    _center(client, planner)
    res = client.get("/api/v1/farm-centers/export.xlsx", headers=planner)
    assert res.status_code == 200
