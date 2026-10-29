"""Crea los eventos del plan y los avisos internos de la campana.

No son tablas temporales (ADR 0001, decisión 4).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "change_events",
        sa.Column("plant_id", sa.BigInteger(), nullable=False),
        sa.Column("daily_plan_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            mssql.DATETIME2(precision=3),
            server_default=sa.text("sysutcdatetime()"),
            nullable=False,
        ),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False, start=1, increment=1), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('plan.published', 'plan.changed', 'plan.closed')",
            name=op.f("ck_change_events_event_type"),
        ),
        sa.ForeignKeyConstraint(
            ["daily_plan_id"],
            ["plan.daily_plans.id"],
            name=op.f("fk_change_events_daily_plan_id_daily_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["master.plants.id"], name=op.f("fk_change_events_plant_id_plants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_change_events")),
        schema="plan",
    )
    op.create_index(
        "ix_change_events_daily_plan_id", "change_events", ["daily_plan_id"], unique=False, schema="plan"
    )
    op.create_table(
        "notifications",
        sa.Column("plant_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("change_event_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.String(length=600), nullable=True),
        sa.Column("link", sa.String(length=300), nullable=True),
        sa.Column("read_at", mssql.DATETIME2(precision=3), nullable=True),
        sa.Column(
            "created_at",
            mssql.DATETIME2(precision=3),
            server_default=sa.text("sysutcdatetime()"),
            nullable=False,
        ),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False, start=1, increment=1), nullable=False),
        sa.ForeignKeyConstraint(
            ["change_event_id"],
            ["plan.change_events.id"],
            name=op.f("fk_notifications_change_event_id_change_events"),
        ),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["master.plants.id"], name=op.f("fk_notifications_plant_id_plants")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["core.users.id"], name=op.f("fk_notifications_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        schema="plan",
    )
    op.create_index(
        op.f("ix_notifications_change_event_id"),
        "notifications",
        ["change_event_id"],
        unique=False,
        schema="plan",
    )
    op.create_index(
        "ix_notifications_user_id_read_at",
        "notifications",
        ["user_id", "read_at"],
        unique=False,
        schema="plan",
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_id_read_at", table_name="notifications", schema="plan")
    op.drop_index(op.f("ix_notifications_change_event_id"), table_name="notifications", schema="plan")
    op.drop_table("notifications", schema="plan")
    op.drop_index("ix_change_events_daily_plan_id", table_name="change_events", schema="plan")
    op.drop_table("change_events", schema="plan")
