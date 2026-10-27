"""Errores de la aplicación y su traducción al formato único de respuesta.

Toda respuesta de error tiene la forma `{code, message, details, field_errors}`.
"""

import logging
from collections.abc import Sequence
from http import HTTPStatus
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class FieldError(BaseModel):
    field: str
    message: str
    code: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
    field_errors: list[FieldError] = []


class AppError(Exception):
    status_code = 400
    code = "bad_request"
    message = "Solicitud inválida."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        field_errors: Sequence[FieldError] = (),
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details
        self.field_errors = list(field_errors)
        super().__init__(self.message)


class AuthenticationError(AppError):
    status_code = 401
    code = "not_authenticated"
    message = "Debe iniciar sesión."


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"
    message = "No tiene permiso para realizar esta acción."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "El registro no existe."


class ConflictError(AppError):
    """Conflicto de concurrencia o de unicidad.

    En concurrencia, `details.current` lleva los datos vigentes del registro.
    """

    status_code = 409
    code = "conflict"
    message = "El registro fue modificado por otro usuario. Revise los datos actuales."


class BusinessRuleError(AppError):
    status_code = 422
    code = "business_rule_violation"
    message = "La operación no cumple una regla de negocio."


# Mensajes en español para los errores de validación más comunes de Pydantic.
_VALIDATION_MESSAGES: dict[str, str] = {
    "missing": "Campo obligatorio.",
    "string_too_short": "Debe tener al menos {min_length} caracteres.",
    "string_too_long": "Debe tener como máximo {max_length} caracteres.",
    "string_type": "Debe ser texto.",
    "int_type": "Debe ser un número entero.",
    "int_parsing": "Debe ser un número entero.",
    "float_parsing": "Debe ser un número.",
    "decimal_parsing": "Debe ser un número decimal.",
    "decimal_type": "Debe ser un número decimal.",
    "decimal_max_places": "Admite como máximo {decimal_places} decimales.",
    "decimal_max_digits": "Admite como máximo {max_digits} dígitos.",
    "greater_than": "Debe ser mayor que {gt}.",
    "greater_than_equal": "Debe ser mayor o igual que {ge}.",
    "less_than": "Debe ser menor que {lt}.",
    "less_than_equal": "Debe ser menor o igual que {le}.",
    "bool_parsing": "Debe ser verdadero o falso.",
    "date_from_datetime_parsing": "Fecha inválida (formato AAAA-MM-DD).",
    "date_parsing": "Fecha inválida (formato AAAA-MM-DD).",
    "datetime_parsing": "Fecha y hora inválidas (ISO 8601).",
    "time_parsing": "Hora inválida (formato HH:MM).",
    "literal_error": "Valor no permitido.",
    "enum": "Valor no permitido.",
    "value_error": "Valor inválido.",
    "json_invalid": "El cuerpo de la solicitud no es JSON válido.",
    "extra_forbidden": "Campo no permitido.",
}


def _field_path(loc: Sequence[int | str]) -> str:
    # El primer elemento indica el origen (body, query, path): no forma parte del nombre del campo.
    parts = list(loc[1:]) if loc and loc[0] in {"body", "query", "path", "header", "cookie"} else list(loc)
    return ".".join(str(p) for p in parts) or "__root__"


def validation_field_errors(errors: Sequence[Any]) -> list[FieldError]:
    result: list[FieldError] = []
    for err in errors:
        code = str(err.get("type", "value_error"))
        template = _VALIDATION_MESSAGES.get(code)
        ctx = err.get("ctx") or {}
        try:
            message = template.format(**ctx) if template else str(err.get("msg", "Valor inválido."))
        except (KeyError, IndexError):
            message = template or "Valor inválido."
        result.append(FieldError(field=_field_path(err.get("loc", ())), message=message, code=code))
    return result


_HTTP_CODES: dict[int, tuple[str, str]] = {
    400: ("bad_request", "Solicitud inválida."),
    401: ("not_authenticated", "Debe iniciar sesión."),
    403: ("permission_denied", "No tiene permiso para realizar esta acción."),
    404: ("not_found", "El recurso no existe."),
    405: ("method_not_allowed", "Método no permitido."),
    409: ("conflict", "Conflicto con el estado actual del recurso."),
    413: ("payload_too_large", "El archivo supera el tamaño máximo permitido."),
    429: ("too_many_requests", "Demasiadas solicitudes. Intente más tarde."),
}


def _response(status_code: int, body: ErrorResponse, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"), headers=headers)


# Cada handler se registra para un tipo de excepción concreto; el cast solo informa ese tipo a mypy.


async def _app_error_handler(_request: Request, error: Exception) -> JSONResponse:
    exc = cast(AppError, error)
    return _response(
        exc.status_code,
        ErrorResponse(code=exc.code, message=exc.message, details=exc.details, field_errors=exc.field_errors),
    )


async def _validation_error_handler(_request: Request, error: Exception) -> JSONResponse:
    exc = cast(RequestValidationError, error)
    return _response(
        422,
        ErrorResponse(
            code="validation_error",
            message="Hay campos con errores.",
            field_errors=validation_field_errors(exc.errors()),
        ),
    )


async def _http_error_handler(_request: Request, error: Exception) -> JSONResponse:
    exc = cast(StarletteHTTPException, error)
    code, default_message = _HTTP_CODES.get(exc.status_code, ("http_error", "Error en la solicitud."))
    # Starlette usa la frase estándar en inglés ("Not Found") cuando no se da un detalle propio.
    custom = isinstance(exc.detail, str) and exc.detail != HTTPStatus(exc.status_code).phrase
    message = exc.detail if custom else default_message
    return _response(
        exc.status_code, ErrorResponse(code=code, message=message), headers=getattr(exc, "headers", None)
    )


async def _stale_data_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return _response(409, ErrorResponse(code=ConflictError.code, message=ConflictError.message))


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no controlado", extra={"path": request.url.path}, exc_info=exc)
    return _response(500, ErrorResponse(code="internal_error", message="Error interno. Intente nuevamente."))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(StaleDataError, _stale_data_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
