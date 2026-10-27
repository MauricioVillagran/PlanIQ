"""Roles y permisos granulares. El catálogo de permisos lo crean las migraciones; la matriz la edita Admin."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import ActiveMixin, AuditMixin, IdMixin, RowVersionMixin
from app.db.types import UtcDateTime


class Permission(IdMixin, Base):
    __tablename__ = "permissions"
    __table_args__ = {"schema": "core"}

    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(400))
    module: Mapped[str] = mapped_column(String(50), nullable=False)


class Role(IdMixin, AuditMixin, ActiveMixin, RowVersionMixin, Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": "core"}

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(400))
    # Roles base de la especificación: no se desactivan, pero su matriz de permisos es editable.
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false(), default=False)

    permissions: Mapped[list[Permission]] = relationship(secondary="core.role_permissions", lazy="selectin")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    # Los cambios se auditan en el rol (relación `permissions`).
    __audit__ = False
    __table_args__ = {"schema": "core"}

    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.permissions.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, server_default=func.sysutcdatetime()
    )
    created_by: Mapped[int | None] = mapped_column(BigInteger)
