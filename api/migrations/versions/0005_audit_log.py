"""Crea el registro de auditoría core.audit_log.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column(
            "occurred_at",
            mssql.DATETIME2(precision=3),
            server_default=sa.text("sysutcdatetime()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("entity", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("plant_id", sa.BigInteger(), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False, start=1, increment=1), nullable=False),
        sa.CheckConstraint(
            "action IN ('create', 'update', 'deactivate', 'activate', 'delete')",
            name=op.f("ck_audit_log_action"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
        schema="core",
    )
    op.create_index(
        "ix_audit_log_entity_entity_id_occurred_at",
        "audit_log",
        ["entity", "entity_id", "occurred_at"],
        unique=False,
        schema="core",
    )
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"], unique=False, schema="core")
    op.create_index(
        "ix_audit_log_user_id_occurred_at",
        "audit_log",
        ["user_id", "occurred_at"],
        unique=False,
        schema="core",
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_user_id_occurred_at", table_name="audit_log", schema="core")
    op.drop_index("ix_audit_log_occurred_at", table_name="audit_log", schema="core")
    op.drop_index("ix_audit_log_entity_entity_id_occurred_at", table_name="audit_log", schema="core")
    op.drop_table("audit_log", schema="core")
