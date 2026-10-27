import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import register_error_handlers
from app.core.logging import JsonFormatter, request_id_var
from app.core.pagination import Page, PageParamsDep
from app.core.types import DecimalStr
from app.db.types import UtcDateTime
from app.modules.jobs.runner import retry_delay


class Weight(BaseModel):
    kg: DecimalStr


def test_decimal_is_serialized_as_string_without_losing_precision() -> None:
    assert Weight(kg=Decimal("1234.500")).model_dump(mode="json") == {"kg": "1234.500"}
    assert Weight.model_validate({"kg": "0.1"}).kg == Decimal("0.1")
    assert Weight.model_validate({"kg": 2}).kg == Decimal(2)


def test_decimal_openapi_schema_is_string() -> None:
    schema = Weight.model_json_schema(mode="serialization")
    assert schema["properties"]["kg"]["type"] == "string"


def _pagination_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/items")
    def items(params: PageParamsDep) -> Page[int]:
        data = list(range(1, 101))
        return Page.build(data[params.offset : params.offset + params.page_size], params, total=len(data))

    return app


def test_pagination_slices_and_reports_total() -> None:
    client = TestClient(_pagination_app())
    body = client.get("/items", params={"page": 3, "page_size": 10}).json()
    assert body == {"items": list(range(21, 31)), "page": 3, "page_size": 10, "total": 100}


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 201}])
def test_pagination_rejects_out_of_range(params: dict[str, int]) -> None:
    res = TestClient(_pagination_app()).get("/items", params=params)
    assert res.status_code == 422


def test_json_formatter_includes_extras_and_request_id() -> None:
    record = logging.makeLogRecord(
        {"name": "test", "levelname": "INFO", "msg": "Plan %s", "args": ("publicado",), "plan_id": 7}
    )
    token = request_id_var.set("req-1")
    try:
        line = json.loads(JsonFormatter("api").format(record))
    finally:
        request_id_var.reset(token)
    assert line["msg"] == "Plan publicado"
    assert line["plan_id"] == 7
    assert line["request_id"] == "req-1"
    assert line["service"] == "api"


def test_utc_datetime_rejects_naive_values() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        UtcDateTime().process_bind_param(datetime(2026, 10, 26, 12, 0), None)  # type: ignore[arg-type]


def test_utc_datetime_converts_to_utc() -> None:
    santiago_summer = datetime(2026, 12, 1, 9, 0, tzinfo=UTC) + timedelta(hours=-3)
    stored = UtcDateTime().process_bind_param(santiago_summer, None)  # type: ignore[arg-type]
    assert stored == datetime(2026, 12, 1, 6, 0)


@pytest.mark.parametrize(
    ("attempt", "expected"),
    [
        (1, timedelta(seconds=30)),
        (2, timedelta(seconds=60)),
        (3, timedelta(seconds=120)),
        (10, timedelta(minutes=15)),
    ],
)
def test_retry_delay_is_exponential_with_cap(attempt: int, expected: timedelta) -> None:
    assert retry_delay(attempt) == expected
