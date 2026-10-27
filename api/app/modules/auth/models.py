"""Refresh tokens: se guarda solo el hash. Cada rotación crea uno nuevo en la misma familia;
reutilizar uno ya rotado revoca la familia completa (señal de robo del token)."""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import IdMixin
from app.db.types import UtcDateTime


class RefreshToken(IdMixin, Base):
    __tablename__ = "refresh_tokens"
    # Sesiones: se registran en el log de la API, no en la auditoría de datos.
    __audit__ = False
    __table_args__ = (
        Index("ix_refresh_tokens_user_id_revoked_at", "user_id", "revoked_at"),
        {"schema": "core"},
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    family_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, server_default=func.sysutcdatetime()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    user_agent: Mapped[str | None] = mapped_column(String(400))
    ip_address: Mapped[str | None] = mapped_column(String(45))
