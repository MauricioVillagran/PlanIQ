"""Usuarios propios del sistema, sus roles y las plantas a las que tienen acceso."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, SmallInteger, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import ActiveMixin, AuditMixin, IdMixin, RowVersionMixin
from app.db.types import UtcDateTime
from app.modules.plants.models import Plant
from app.modules.roles.models import Role


class User(IdMixin, AuditMixin, ActiveMixin, RowVersionMixin, Base):
    __tablename__ = "users"
    # Cada ingreso actualiza estos campos: no se auditan (el bloqueo sí, vía locked_at).
    __audit_exclude__ = frozenset({"last_login_at", "failed_login_count"})
    # Se registra que cambió, nunca el valor.
    __audit_mask__ = frozenset({"password_hash"})
    __table_args__ = {"schema": "core"}

    # Se guardan en minúsculas: el ingreso no distingue mayúsculas.
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=true(), default=True
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    failed_login_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="0", default=0
    )
    locked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    last_login_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    roles: Mapped[list[Role]] = relationship(secondary="core.user_roles", lazy="selectin")
    plants: Mapped[list[Plant]] = relationship(secondary="core.user_plants", lazy="selectin")


class UserRole(Base):
    __tablename__ = "user_roles"
    # Los cambios se auditan en el usuario (relación `roles`).
    __audit__ = False
    __table_args__ = {"schema": "core"}

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("core.roles.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, server_default=func.sysutcdatetime()
    )
    created_by: Mapped[int | None] = mapped_column(BigInteger)


class UserPlant(Base):
    __tablename__ = "user_plants"
    # Los cambios se auditan en el usuario (relación `plants`).
    __audit__ = False
    __table_args__ = {"schema": "core"}

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.users.id", ondelete="CASCADE"), primary_key=True
    )
    plant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("master.plants.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, server_default=func.sysutcdatetime()
    )
    created_by: Mapped[int | None] = mapped_column(BigInteger)
