"""Creación de la aplicación FastAPI."""

from fastapi import APIRouter, FastAPI

from app.core.config import get_settings
from app.core.errors import ErrorResponse, register_error_handlers
from app.core.logging import setup_logging
from app.core.middleware import register_middleware
from app.modules.auth.router import router as auth_router
from app.modules.auth.security import RateLimiter
from app.modules.health.router import router as health_router

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging("api", settings.log_level)

    app = FastAPI(
        title="PlanIQ API",
        version="0.1.0",
        description="API de planificación productiva de planta. Errores con formato único `ErrorResponse`.",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
        responses={
            422: {"model": ErrorResponse, "description": "Error de validación"},
            500: {"model": ErrorResponse, "description": "Error interno"},
        },
    )
    app.state.login_limiter = RateLimiter(settings.auth_login_rate_limit)
    register_middleware(app)
    register_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    api.include_router(health_router)
    api.include_router(auth_router)
    app.include_router(api)
    return app


app = create_app()
