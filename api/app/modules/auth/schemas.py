from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50, examples=["admin"])
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    """El refresh token no viaja en el cuerpo: va en una cookie httpOnly."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105 (tipo de token, no una clave)
    expires_in: int = Field(description="Segundos de validez del token de acceso")
    must_change_password: bool


class RoleRef(BaseModel):
    code: str
    name: str


class PlantRef(BaseModel):
    id: int
    code: str
    name: str


class MeResponse(BaseModel):
    id: int
    username: str
    full_name: str
    email: str
    must_change_password: bool
    roles: list[RoleRef]
    permissions: list[str]
    all_plants: bool = Field(description="True si tiene el permiso plants.all")
    plants: list[PlantRef]
