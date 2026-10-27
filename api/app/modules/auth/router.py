"""Endpoints de autenticación: /auth/login, /refresh, /logout, /change-password, /me."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorResponse
from app.db.session import SessionDep
from app.modules.auth.dependencies import CurrentUser, get_current_user_allow_password_change
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    PlantRef,
    RoleRef,
    TokenResponse,
)
from app.modules.auth.security import RateLimiter
from app.modules.auth.service import AuthService, ClientInfo, SessionTokens
from app.modules.plants.models import Plant
from app.modules.roles.models import Role

REFRESH_COOKIE = "planiq_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"

router = APIRouter(prefix="/auth", tags=["auth"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
AllowPasswordChangeUser = Annotated[CurrentUser, Depends(get_current_user_allow_password_change)]
_AUTH_ERRORS: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse, "description": "No autenticado"}
}


class TooManyRequestsError(AppError):
    status_code = 429
    code = "too_many_requests"
    message = "Demasiados intentos de ingreso. Espere un momento e intente nuevamente."


def _client(request: Request) -> ClientInfo:
    return ClientInfo(
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )


def _token_response(response: Response, tokens: SessionTokens, settings: Settings) -> TokenResponse:
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=settings.jwt_refresh_ttl_hours * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
    )
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
        must_change_password=tokens.must_change_password,
    )


def _login_limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.app.state.login_limiter
    return limiter


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Ingresar con usuario y contraseña",
    responses={**_AUTH_ERRORS, 429: {"model": ErrorResponse, "description": "Demasiados intentos"}},
)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    limiter: Annotated[RateLimiter, Depends(_login_limiter)],
) -> TokenResponse:
    client = _client(request)
    if not limiter.hit(client.ip_address or "unknown"):
        raise TooManyRequestsError()
    tokens = AuthService(session, settings).login(body.username, body.password, client)
    return _token_response(response, tokens, settings)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar el token de acceso con la cookie de sesión",
    responses=_AUTH_ERRORS,
)
def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    planiq_refresh: Annotated[str | None, Cookie()] = None,
) -> TokenResponse:
    tokens = AuthService(session, settings).refresh(planiq_refresh, _client(request))
    return _token_response(response, tokens, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Cerrar la sesión")
def logout(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    planiq_refresh: Annotated[str | None, Cookie()] = None,
) -> None:
    AuthService(session, settings).logout(planiq_refresh)
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
    )


@router.post(
    "/change-password",
    response_model=TokenResponse,
    summary="Cambiar la contraseña (obligatorio en el primer ingreso)",
    responses={**_AUTH_ERRORS, 422: {"model": ErrorResponse, "description": "No cumple la política"}},
)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: AllowPasswordChangeUser,
    session: SessionDep,
    settings: SettingsDep,
) -> TokenResponse:
    tokens = AuthService(session, settings).change_password(
        user.id, body.current_password, body.new_password, _client(request)
    )
    return _token_response(response, tokens, settings)


@router.get(
    "/me", response_model=MeResponse, summary="Usuario actual, permisos y plantas", responses=_AUTH_ERRORS
)
def me(user: AllowPasswordChangeUser, session: SessionDep) -> MeResponse:
    roles = session.scalars(select(Role).where(Role.code.in_(user.role_codes)).order_by(Role.name)).all()
    plants_query = select(Plant).where(Plant.is_active).order_by(Plant.name)
    if user.plant_ids is not None:
        plants_query = plants_query.where(Plant.id.in_(user.plant_ids))
    plants = session.scalars(plants_query).all()
    return MeResponse(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        must_change_password=user.must_change_password,
        roles=[RoleRef(code=r.code, name=r.name) for r in roles],
        permissions=sorted(user.permissions),
        all_plants=user.plant_ids is None,
        plants=[PlantRef(id=p.id, code=p.code, name=p.name) for p in plants],
    )
