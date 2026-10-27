from decimal import Decimal
from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.errors import ConflictError, NotFoundError, register_error_handlers
from app.core.middleware import register_middleware


class HarvestLineIn(BaseModel):
    fish_count: int = Field(gt=0)
    avg_weight_kg: Decimal = Field(max_digits=10, decimal_places=3)
    cage_code: str = Field(min_length=2)


def _app() -> FastAPI:
    app = FastAPI()
    register_middleware(app)
    register_error_handlers(app)

    @app.post("/lines")
    def create_line(line: HarvestLineIn) -> HarvestLineIn:
        return line

    @app.get("/missing")
    def missing() -> None:
        raise NotFoundError("La planta no existe.")

    @app.get("/conflict")
    def conflict() -> None:
        raise ConflictError(details={"current": {"name": "Planta A"}})

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("detalle interno que no debe filtrarse")

    @app.get("/search")
    def search(page: Annotated[int, Query(ge=1)] = 1) -> dict[str, int]:
        return {"page": page}

    return app


client = TestClient(_app(), raise_server_exceptions=False)


def test_validation_error_has_unified_format_with_spanish_messages() -> None:
    res = client.post("/lines", json={"fish_count": 0, "avg_weight_kg": "4.12345"})
    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "Hay campos con errores."
    errors = {e["field"]: e for e in body["field_errors"]}
    assert errors["fish_count"]["message"] == "Debe ser mayor que 0."
    assert errors["fish_count"]["code"] == "greater_than"
    assert errors["avg_weight_kg"]["message"] == "Admite como máximo 3 decimales."
    assert errors["cage_code"]["message"] == "Campo obligatorio."


def test_query_param_errors_use_param_name() -> None:
    res = client.get("/search", params={"page": 0})
    assert res.status_code == 422
    assert res.json()["field_errors"][0]["field"] == "page"


def test_app_error_keeps_custom_message() -> None:
    res = client.get("/missing")
    assert res.status_code == 404
    assert res.json() == {
        "code": "not_found",
        "message": "La planta no existe.",
        "details": None,
        "field_errors": [],
    }


def test_conflict_carries_current_data() -> None:
    res = client.get("/conflict")
    assert res.status_code == 409
    assert res.json()["details"] == {"current": {"name": "Planta A"}}


def test_unknown_route_returns_spanish_not_found() -> None:
    res = client.get("/no-existe")
    assert res.status_code == 404
    assert res.json()["code"] == "not_found"
    assert res.json()["message"] == "El recurso no existe."


def test_unhandled_error_does_not_leak_details() -> None:
    res = client.get("/boom")
    assert res.status_code == 500
    assert res.json()["code"] == "internal_error"
    assert "detalle interno" not in res.text


def test_request_id_is_generated_and_echoed() -> None:
    assert len(client.get("/search").headers["X-Request-ID"]) == 32
    assert client.get("/search", headers={"X-Request-ID": "abc-123"}).headers["X-Request-ID"] == "abc-123"
