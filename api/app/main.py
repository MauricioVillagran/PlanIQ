"""Creación de la aplicación FastAPI."""

from fastapi import APIRouter, FastAPI

from app.core.config import get_settings
from app.core.errors import ErrorResponse, register_error_handlers
from app.core.logging import setup_logging
from app.core.middleware import register_middleware
from app.modules.audit.listener import register_audit_listeners
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.auth.security import RateLimiter
from app.modules.farms.router import router as farms_router
from app.modules.health.router import router as health_router
from app.modules.parameters.router import router as parameters_router
from app.modules.plants.router import router as plants_router
from app.modules.roles.router import permissions_router
from app.modules.roles.router import router as roles_router
from app.modules.shifts.router import router as shifts_router
from app.modules.users.router import router as users_router

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging("api", settings.log_level)
    register_audit_listeners()

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
    api.include_router(audit_router)
    api.include_router(users_router)
    api.include_router(roles_router)
    api.include_router(permissions_router)
    api.include_router(plants_router)
    api.include_router(shifts_router)
    api.include_router(parameters_router)
    api.include_router(farms_router)
    app.include_router(api)
    return app


app = create_app()
