"""Fixtures de integración: cliente HTTP sobre la base de test y fábricas de datos ficticios."""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.main import create_app
from app.modules.auth.security import hash_password
from app.modules.plants.models import Plant
from app.modules.roles.models import Role
from app.modules.users.models import User

TEST_PASSWORD = "Clave-de-prueba-1"


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    application = create_app()
    application.dependency_overrides[get_session] = lambda: db_session
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_plant(db_session: Session) -> Callable[..., Plant]:
    def factory(code: str, name: str | None = None, **kwargs: Any) -> Plant:
        plant = Plant(code=code, name=name or f"Planta {code}", plant_type="own", **kwargs)
        db_session.add(plant)
        db_session.flush()
        return plant

    return factory


@pytest.fixture
def make_user(db_session: Session) -> Callable[..., User]:
    def factory(
        username: str,
        *,
        roles: tuple[str, ...] = (),
        plants: tuple[Plant, ...] = (),
        password: str = TEST_PASSWORD,
        must_change_password: bool = False,
        **kwargs: Any,
    ) -> User:
        user = User(
            username=username,
            email=f"{username}@example.com",
            full_name=username.title(),
            password_hash=hash_password(password),
            must_change_password=must_change_password,
            **kwargs,
        )
        user.roles.extend(db_session.scalars(select(Role).where(Role.code.in_(roles))).all())
        user.plants.extend(plants)
        db_session.add(user)
        db_session.commit()
        return user

    return factory


def login(client: TestClient, username: str, password: str = TEST_PASSWORD) -> dict[str, Any]:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    body: dict[str, Any] = res.json()
    return body


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
