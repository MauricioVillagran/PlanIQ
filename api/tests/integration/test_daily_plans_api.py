"""API del plan diario en Borrador: creación, líneas, validaciones, orden, vista semanal y permisos."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.farms.models import Cage, FarmCenter, HoldingCage
from app.modules.parameters.models import Parameter
from app.modules.plants.models import Plant
from app.modules.shifts.models import Shift
from app.modules.users.models import User
from tests.integration.conftest import auth_header, login

pytestmark = pytest.mark.integration

DAY = "2026-11-02"


@dataclass
class Setup:
    plant: Plant
    north: FarmCenter
    south: FarmCenter
    cages: dict[str, Cage]
    holding: HoldingCage
    small_holding: HoldingCage
    day: Shift
    night: Shift
    token: str


@pytest.fixture
def setup(
    db_session: Session, make_plant: Callable[..., Plant], make_user: Callable[..., User], client: TestClient
) -> Setup:
    plant = make_plant("PD")
    north = FarmCenter(code="CN", name="Centro Norte")
    south = FarmCenter(code="CS", name="Centro Sur")
    db_session.add_all([north, south])
    db_session.flush()
    cages = {
        "N1": Cage(farm_center_id=north.id, code="N1"),
        "N2": Cage(farm_center_id=north.id, code="N2"),
        "S1": Cage(farm_center_id=south.id, code="S1"),
    }
    holding = HoldingCage(plant_id=plant.id, code="A1", capacity_fish=40_000)
    small = HoldingCage(plant_id=plant.id, code="A2", capacity_fish=10_000)
    day = Shift(plant_id=plant.id, name="Día", start_time=time(7), end_time=time(19), crosses_midnight=False)
    night = Shift(
        plant_id=plant.id,
        name="Noche",
        start_time=time(19),
        end_time=time(7),
        crosses_midnight=True,
        sort_order=1,
    )
    params = [
        Parameter(key="harvest.wfe_factor", plant_id=plant.id, value_type="decimal", value="0.9"),
        Parameter(key="harvest.avg_weight_kg.min", plant_id=plant.id, value_type="decimal", value="2"),
        Parameter(key="harvest.avg_weight_kg.max", plant_id=plant.id, value_type="decimal", value="8"),
    ]
    db_session.add_all([*cages.values(), holding, small, day, night, *params])
    db_session.commit()
    make_user("planificadora", roles=("planning",), plants=(plant,))
    token = login(client, "planificadora")["access_token"]
    return Setup(plant, north, south, cages, holding, small, day, night, token)


def _url(s: Setup, day: str = DAY) -> str:
    return f"/api/v1/plants/{s.plant.id}/daily-plans/{day}"


def _create(client: TestClient, s: Setup, day: str = DAY, **body: Any) -> dict[str, Any]:
    res = client.post(_url(s, day), headers=auth_header(s.token), json=body)
    assert res.status_code == 201, res.text
    data: dict[str, Any] = res.json()
    return data


def _line(
    s: Setup,
    cage: str,
    fish: int,
    weight: str,
    *,
    shift: Shift | None = None,
    holding: HoldingCage | None = None,
) -> dict[str, Any]:
    return {
        "cage_id": s.cages[cage].id,
        "holding_cage_id": (holding or s.holding).id,
        "shift_id": (shift or s.day).id,
        "fish_count": fish,
        "avg_weight_kg": weight,
    }


def _add(client: TestClient, s: Setup, plan_id: int, line: dict[str, Any]) -> Any:
    return client.post(
        f"/api/v1/daily-plans/{plan_id}/harvest-entries", headers=auth_header(s.token), json=line
    )


def test_create_empty_plan_and_read_it(client: TestClient, setup: Setup) -> None:
    body = _create(client, setup)
    assert body["plan"]["status"] == "draft"
    assert body["plan"]["current_version"] == 0
    assert body["entries"] == []
    assert body["summary"]["day"]["fish_count"] == 0

    again = client.get(_url(setup), headers=auth_header(setup.token))
    assert again.status_code == 200
    assert again.json()["plan"]["id"] == body["plan"]["id"]

    duplicate = client.post(_url(setup), headers=auth_header(setup.token), json={})
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "plan_exists"


def test_missing_plan_is_404(client: TestClient, setup: Setup) -> None:
    res = client.get(_url(setup, "2026-12-01"), headers=auth_header(setup.token))
    assert res.status_code == 404
    assert res.json()["code"] == "plan_not_found"


def test_lines_compute_biomass_wfe_and_totals_like_a_manual_check(client: TestClient, setup: Setup) -> None:
    plan_id = _create(client, setup)["plan"]["id"]
    first = _add(client, setup, plan_id, _line(setup, "N1", 12_000, "4.850"))
    assert first.status_code == 201, first.text
    assert first.json()["entry"]["biomass_kg"] == "58200.000"
    assert first.json()["entry"]["farm_center_code"] == "CN"
    assert first.json()["entry"]["sequence"] == 1
    _add(client, setup, plan_id, _line(setup, "S1", 9_500, "5.120", shift=setup.night))

    summary = client.get(f"/api/v1/daily-plans/{plan_id}/summary", headers=auth_header(setup.token)).json()
    # Control manual: 12.000 × 4,850 = 58.200; 9.500 × 5,120 = 48.640; total 106.840; WFE × 0,9 = 96.156.
    assert summary["day"]["fish_count"] == 21_500
    assert summary["day"]["biomass_kg"] == "106840.000"
    assert summary["day"]["wfe_kg"] == "96156.000"
    assert [g["label"] for g in summary["by_shift"]] == ["Día", "Noche"]
    assert [g["label"] for g in summary["by_center"]] == ["CN", "CS"]
    assert summary["has_errors"] is False
    assert summary["issues"] == []


def test_holding_capacity_and_weight_range_block_the_line(client: TestClient, setup: Setup) -> None:
    plan_id = _create(client, setup)["plan"]["id"]
    _add(client, setup, plan_id, _line(setup, "N1", 8_000, "4.5", holding=setup.small_holding))

    over = _add(client, setup, plan_id, _line(setup, "N2", 3_000, "4.5", holding=setup.small_holding))
    assert over.status_code == 422
    assert over.json()["code"] == "harvest_entry_invalid"
    assert "A2" in over.json()["message"]
    assert over.json()["field_errors"][0]["field"] == "fish_count"

    heavy = _add(client, setup, plan_id, _line(setup, "N2", 1_000, "8.000"))
    assert heavy.status_code == 422
    assert heavy.json()["field_errors"][0]["field"] == "avg_weight_kg"

    # Otro turno: el acopio vuelve a tener capacidad.
    ok = _add(
        client,
        setup,
        plan_id,
        _line(setup, "N2", 3_000, "4.5", shift=setup.night, holding=setup.small_holding),
    )
    assert ok.status_code == 201


def test_repeated_cage_only_warns(client: TestClient, setup: Setup) -> None:
    plan_id = _create(client, setup)["plan"]["id"]
    _add(client, setup, plan_id, _line(setup, "N1", 5_000, "4.5"))
    res = _add(client, setup, plan_id, _line(setup, "N1", 4_000, "4.6", shift=setup.night))
    assert res.status_code == 201
    issues = res.json()["summary"]["issues"]
    assert [(i["code"], i["severity"]) for i in issues] == [("cage_repeated", "warning")]
    assert len(issues[0]["entry_ids"]) == 2


def test_update_with_stale_row_version_is_409_with_current_data(client: TestClient, setup: Setup) -> None:
    plan_id = _create(client, setup)["plan"]["id"]
    entry = _add(client, setup, plan_id, _line(setup, "N1", 5_000, "4.5")).json()["entry"]
    url = f"/api/v1/daily-plans/{plan_id}/harvest-entries/{entry['id']}"

    first = client.patch(
        url, headers=auth_header(setup.token), json={"row_version": entry["row_version"], "fish_count": 6_000}
    )
    assert first.status_code == 200
    assert first.json()["entry"]["fish_count"] == 6_000

    stale = client.patch(
        url, headers=auth_header(setup.token), json={"row_version": entry["row_version"], "fish_count": 7_000}
    )
    assert stale.status_code == 409
    assert stale.json()["details"]["current"]["fish_count"] == 6_000


def test_delete_and_reorder_keep_a_continuous_sequence(client: TestClient, setup: Setup) -> None:
    plan_id = _create(client, setup)["plan"]["id"]
    ids = [
        _add(client, setup, plan_id, _line(setup, c, 1_000, "4")).json()["entry"] for c in ("N1", "N2", "S1")
    ]

    res = client.put(
        f"/api/v1/daily-plans/{plan_id}/harvest-entries/order",
        headers=auth_header(setup.token),
        json={"entry_ids": [ids[2]["id"], ids[0]["id"], ids[1]["id"]]},
    )
    assert res.status_code == 200
    assert [e["cage_code"] for e in res.json()["entries"]] == ["S1", "N1", "N2"]

    current = {e["id"]: e for e in res.json()["entries"]}
    deleted = client.delete(
        f"/api/v1/daily-plans/{plan_id}/harvest-entries/{ids[0]['id']}",
        headers=auth_header(setup.token),
        params={"row_version": current[ids[0]["id"]]["row_version"]},
    )
    assert deleted.status_code == 200
    detail = client.get(f"/api/v1/daily-plans/{plan_id}", headers=auth_header(setup.token)).json()
    assert [(e["cage_code"], e["sequence"]) for e in detail["entries"]] == [("S1", 1), ("N2", 2)]

    partial = client.put(
        f"/api/v1/daily-plans/{plan_id}/harvest-entries/order",
        headers=auth_header(setup.token),
        json={"entry_ids": [ids[2]["id"]]},
    )
    assert partial.status_code == 422


def test_copy_from_previous_day(client: TestClient, setup: Setup) -> None:
    source = _create(client, setup, "2026-11-01")["plan"]["id"]
    _add(client, setup, source, _line(setup, "N1", 5_000, "4.5"))
    _add(client, setup, source, _line(setup, "S1", 4_000, "5", shift=setup.night))

    copy = _create(client, setup, DAY, copy_from="2026-11-01")
    assert copy["plan"]["status"] == "draft"
    assert [(e["cage_code"], e["fish_count"], e["shift_name"]) for e in copy["entries"]] == [
        ("N1", 5_000, "Día"),
        ("S1", 4_000, "Noche"),
    ]

    missing = client.post(
        _url(setup, "2026-11-05"), headers=auth_header(setup.token), json={"copy_from": "2026-10-01"}
    )
    assert missing.status_code == 422
    assert missing.json()["code"] == "copy_source_not_found"


def test_full_coverage_required_blocks_creation_when_shifts_have_gaps(
    client: TestClient, setup: Setup, db_session: Session
) -> None:
    setup.night.end_time = time(5)
    db_session.add(
        Parameter(key="shifts.full_coverage", plant_id=setup.plant.id, value_type="bool", value="true")
    )
    db_session.commit()
    res = client.post(_url(setup), headers=auth_header(setup.token), json={})
    assert res.status_code == 422
    assert res.json()["code"] == "shift_coverage_incomplete"


def test_week_view_lists_each_day(client: TestClient, setup: Setup) -> None:
    plan_id = _create(client, setup)["plan"]["id"]
    _add(client, setup, plan_id, _line(setup, "N1", 5_000, "4"))
    res = client.get(
        f"/api/v1/plants/{setup.plant.id}/daily-plans",
        headers=auth_header(setup.token),
        params={"from": "2026-11-01", "to": "2026-11-07"},
    )
    assert res.status_code == 200
    days = res.json()
    assert len(days) == 7
    assert days[0]["plan_id"] is None
    assert days[1]["status"] == "draft"
    assert days[1]["totals"]["biomass_kg"] == "20000.000"


def test_draft_is_hidden_from_roles_that_cannot_edit(
    client: TestClient, setup: Setup, make_user: Callable[..., User]
) -> None:
    _create(client, setup)
    make_user("produccion", roles=("production",), plants=(setup.plant,))
    token = login(client, "produccion")["access_token"]
    assert client.get(_url(setup), headers=auth_header(token)).status_code == 404
    assert client.post(_url(setup, "2026-11-09"), headers=auth_header(token), json={}).status_code == 403


def test_plans_of_other_plants_are_not_accessible(
    client: TestClient, setup: Setup, make_plant: Callable[..., Plant], make_user: Callable[..., User]
) -> None:
    plan_id = _create(client, setup)["plan"]["id"]
    other = make_plant("OT")
    make_user("ajena", roles=("planning",), plants=(other,))
    token = login(client, "ajena")["access_token"]
    assert client.get(_url(setup), headers=auth_header(token)).status_code == 403
    assert client.get(f"/api/v1/daily-plans/{plan_id}", headers=auth_header(token)).status_code == 404


# --- Flujo: publicar, cambios con motivo y cerrar --------------------------------------------
# El historial de versiones se prueba con transacciones reales en test_daily_plan_model.py.


def _post(
    client: TestClient, s: Setup, plan_id: int, action: str, body: dict[str, Any], token: str | None = None
) -> Any:
    return client.post(
        f"/api/v1/daily-plans/{plan_id}/{action}", headers=auth_header(token or s.token), json=body
    )


def _plan_with_line(client: TestClient, s: Setup, day: str = DAY) -> dict[str, Any]:
    plan_id = _create(client, s, day)["plan"]["id"]
    _add(client, s, plan_id, _line(s, "N1", 10_000, "4.5"))
    detail: dict[str, Any] = client.get(f"/api/v1/daily-plans/{plan_id}", headers=auth_header(s.token)).json()
    return detail


def test_publish_creates_version_one_and_locks_line_editing(client: TestClient, setup: Setup) -> None:
    detail = _plan_with_line(client, setup)
    plan = detail["plan"]
    res = _post(client, setup, plan["id"], "publish", {"row_version": plan["row_version"]})
    assert res.status_code == 200, res.text
    published = res.json()["plan"]
    assert (published["status"], published["current_version"]) == ("published", 1)
    assert published["published_by"] is not None

    blocked = _add(client, setup, plan["id"], _line(setup, "N2", 1_000, "4"))
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "plan_published"
    again = _post(client, setup, plan["id"], "publish", {"row_version": published["row_version"]})
    assert again.json()["code"] == "plan_already_published"


def test_publish_rejects_empty_plans_errors_and_stale_versions(
    client: TestClient, setup: Setup, db_session: Session
) -> None:
    empty = _create(client, setup, "2026-11-10")["plan"]
    assert (
        _post(client, setup, empty["id"], "publish", {"row_version": empty["row_version"]}).json()["code"]
        == "plan_empty"
    )

    plan = _plan_with_line(client, setup)["plan"]
    stale = _post(client, setup, plan["id"], "publish", {"row_version": "0000000000000001"})
    assert stale.status_code == 409

    # El rango de peso cambia después de cargar la línea: la publicación se bloquea.
    weight_min = next(
        p
        for p in db_session.query(Parameter).filter_by(
            key="harvest.avg_weight_kg.min", plant_id=setup.plant.id
        )
    )
    weight_min.value = "5"
    db_session.commit()
    res = _post(client, setup, plan["id"], "publish", {"row_version": plan["row_version"]})
    assert res.status_code == 422
    assert res.json()["code"] == "plan_has_errors"
    assert res.json()["details"]["issues"][0]["code"] == "avg_weight_out_of_range"


def test_publish_requires_permission(
    client: TestClient, setup: Setup, make_user: Callable[..., User]
) -> None:
    plan = _plan_with_line(client, setup)["plan"]
    make_user("calidad", roles=("quality",), plants=(setup.plant,))
    token = login(client, "calidad")["access_token"]
    assert (
        _post(client, setup, plan["id"], "publish", {"row_version": plan["row_version"]}, token).status_code
        == 403
    )


def test_published_plan_is_visible_to_other_roles(
    client: TestClient, setup: Setup, make_user: Callable[..., User]
) -> None:
    plan = _plan_with_line(client, setup)["plan"]
    _post(client, setup, plan["id"], "publish", {"row_version": plan["row_version"]})
    make_user("produccion", roles=("production",), plants=(setup.plant,))
    token = login(client, "produccion")["access_token"]
    res = client.get(_url(setup), headers=auth_header(token))
    assert res.status_code == 200
    assert res.json()["plan"]["status"] == "published"


def test_changes_need_a_reason_and_create_a_new_version(client: TestClient, setup: Setup) -> None:
    detail = _plan_with_line(client, setup)
    plan = _post(
        client, setup, detail["plan"]["id"], "publish", {"row_version": detail["plan"]["row_version"]}
    ).json()
    entry = plan["entries"][0]
    change = {
        "row_version": plan["plan"]["row_version"],
        "update": [{"id": entry["id"], "row_version": entry["row_version"], "fish_count": 11_000}],
        "add": [_line(setup, "S1", 3_000, "4.2", shift=setup.night)],
    }
    without_reason = _post(client, setup, plan["plan"]["id"], "changes", change)
    assert without_reason.status_code == 422

    res = _post(
        client, setup, plan["plan"]["id"], "changes", change | {"reason": "Ajuste por mortalidad en N1"}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["plan"]["current_version"] == 2
    assert [(e["cage_code"], e["fish_count"], e["sequence"]) for e in body["entries"]] == [
        ("N1", 11_000, 1),
        ("S1", 3_000, 2),
    ]

    # Otro usuario con la versión anterior del plan: conflicto, no se pisan.
    stale = _post(client, setup, plan["plan"]["id"], "changes", change | {"reason": "Cambio concurrente"})
    assert stale.status_code == 409

    versions = client.get(
        f"/api/v1/daily-plans/{plan['plan']['id']}/versions", headers=auth_header(setup.token)
    ).json()
    assert [(v["number"], v["reason"]) for v in versions] == [(2, "Ajuste por mortalidad en N1"), (1, None)]

    current = body["plan"]["row_version"]
    nothing = _post(
        client, setup, plan["plan"]["id"], "changes", {"row_version": current, "reason": "Sin cambios reales"}
    )
    assert nothing.json()["code"] == "no_changes"


def test_changes_are_validated_as_a_whole(client: TestClient, setup: Setup) -> None:
    detail = _plan_with_line(client, setup)
    plan = _post(
        client, setup, detail["plan"]["id"], "publish", {"row_version": detail["plan"]["row_version"]}
    ).json()
    over = {
        "row_version": plan["plan"]["row_version"],
        "reason": "Agregar jaulas al acopio A1",
        "add": [_line(setup, "N2", 20_000, "4"), _line(setup, "S1", 15_000, "4")],
    }
    res = _post(client, setup, plan["plan"]["id"], "changes", over)
    assert res.status_code == 422
    assert res.json()["details"]["issues"][0]["code"] == "holding_cage_capacity_exceeded"


def test_close_only_after_the_productive_day_and_then_immutable(client: TestClient, setup: Setup) -> None:
    future = _plan_with_line(client, setup, "2099-01-05")["plan"]
    future = _post(client, setup, future["id"], "publish", {"row_version": future["row_version"]}).json()[
        "plan"
    ]
    early = _post(client, setup, future["id"], "close", {"row_version": future["row_version"]})
    assert early.json()["code"] == "plan_day_not_finished"

    draft = _plan_with_line(client, setup, "2020-01-06")["plan"]
    assert (
        _post(client, setup, draft["id"], "close", {"row_version": draft["row_version"]}).json()["code"]
        == "plan_not_published"
    )
    past = _post(client, setup, draft["id"], "publish", {"row_version": draft["row_version"]}).json()
    closed = _post(client, setup, draft["id"], "close", {"row_version": past["plan"]["row_version"]})
    assert closed.status_code == 200, closed.text
    assert closed.json()["plan"]["status"] == "closed"
    assert closed.json()["closable_at"] is not None

    entry = past["entries"][0]
    change = {
        "row_version": closed.json()["plan"]["row_version"],
        "reason": "Intento posterior al cierre",
        "update": [{"id": entry["id"], "row_version": entry["row_version"], "fish_count": 1}],
    }
    assert _post(client, setup, draft["id"], "changes", change).json()["code"] == "plan_closed"
