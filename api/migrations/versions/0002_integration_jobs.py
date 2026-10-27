"""Crea la cola de trabajos integration.jobs.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.BigInteger(), sa.Identity(start=1, increment=1), nullable=False),
        sa.Column("job_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("plant_id", sa.BigInteger(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("priority", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("progress", sa.Numeric(precision=5, scale=2), server_default="0", nullable=False),
        sa.Column("progress_message", sa.String(length=400), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.SmallInteger(), server_default="3", nullable=False),
        sa.Column(
            "run_after",
            mssql.DATETIME2(precision=3),
            server_default=sa.text("sysutcdatetime()"),
            nullable=False,
        ),
        sa.Column("started_at", mssql.DATETIME2(precision=3), nullable=True),
        sa.Column("heartbeat_at", mssql.DATETIME2(precision=3), nullable=True),
        sa.Column("finished_at", mssql.DATETIME2(precision=3), nullable=True),
        sa.Column("locked_by", sa.String(length=100), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", mssql.NVARCHAR(), nullable=True),
        sa.Column(
            "created_at",
            mssql.DATETIME2(precision=3),
            server_default=sa.text("sysutcdatetime()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", mssql.DATETIME2(precision=3), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("row_version", mssql.ROWVERSION(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name=op.f("ck_jobs_status"),
        ),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name=op.f("ck_jobs_progress")),
        sa.CheckConstraint("attempts >= 0 AND max_attempts >= 1", name=op.f("ck_jobs_attempts")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        schema="integration",
    )
    op.create_index(
        "ix_jobs_status_run_after", "jobs", ["status", "run_after", "priority"], schema="integration"
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_status_run_after", table_name="jobs", schema="integration")
    op.drop_table("jobs", schema="integration")
