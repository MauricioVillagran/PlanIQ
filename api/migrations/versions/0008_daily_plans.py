"""Crea el plan diario de cosecha: planes, líneas y versiones, con tablas temporales.

`plan.daily_plans` y `plan.harvest_entries` llevan versionado de sistema (ADR 0001, decisión 4): el
historial va al esquema `plan_history`, con columnas de período ocultas y retención definida.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HISTORY_SCHEMA = "plan_history"
TEMPORAL_TABLES = ("daily_plans", "harvest_entries")
# Cuánto se conserva el historial temporal. Revisable con una migración cuando se defina la política
# de respaldo y archivo de producción (operacion.md); se cuida el límite de 10 GB de SQL Server Express.
HISTORY_RETENTION = "5 YEARS"


def _audit_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False, start=1, increment=1), nullable=False),
        sa.Column(
            "created_at",
            mssql.DATETIME2(precision=3),
            server_default=sa.text("sysutcdatetime()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", mssql.DATETIME2(precision=3), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
    ]


def _make_temporal(table: str) -> None:
    op.execute(
        f"""
        ALTER TABLE [plan].{table} ADD
            valid_from DATETIME2(7) GENERATED ALWAYS AS ROW START HIDDEN NOT NULL
                CONSTRAINT df_{table}_valid_from DEFAULT SYSUTCDATETIME(),
            valid_to DATETIME2(7) GENERATED ALWAYS AS ROW END HIDDEN NOT NULL
                CONSTRAINT df_{table}_valid_to DEFAULT CONVERT(DATETIME2(7), '9999-12-31 23:59:59.9999999'),
            PERIOD FOR SYSTEM_TIME (valid_from, valid_to)
        """
    )
    op.execute(
        f"""
        ALTER TABLE [plan].{table} SET (SYSTEM_VERSIONING = ON (
            HISTORY_TABLE = {HISTORY_SCHEMA}.{table},
            HISTORY_RETENTION_PERIOD = {HISTORY_RETENTION}
        ))
        """
    )


def _drop_temporal(table: str) -> None:
    op.execute(f"ALTER TABLE [plan].{table} SET (SYSTEM_VERSIONING = OFF)")
    op.execute(f"DROP TABLE {HISTORY_SCHEMA}.{table}")


def upgrade() -> None:
    op.execute(f"IF SCHEMA_ID(N'{HISTORY_SCHEMA}') IS NULL EXEC(N'CREATE SCHEMA [{HISTORY_SCHEMA}]')")

    op.create_table(
        "daily_plans",
        sa.Column("plant_id", sa.BigInteger(), nullable=False),
        sa.Column("productive_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("published_at", mssql.DATETIME2(precision=3), nullable=True),
        sa.Column("published_by", sa.BigInteger(), nullable=True),
        sa.Column("closed_at", mssql.DATETIME2(precision=3), nullable=True),
        sa.Column("closed_by", sa.BigInteger(), nullable=True),
        *_audit_columns(),
        sa.Column("row_version", mssql.ROWVERSION(), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'published', 'closed')", name=op.f("ck_daily_plans_status")),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["master.plants.id"], name=op.f("fk_daily_plans_plant_id_plants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_plans")),
        sa.UniqueConstraint("plant_id", "productive_date", name="uq_daily_plans_plant_id_productive_date"),
        schema="plan",
    )
    op.create_table(
        "harvest_entries",
        sa.Column("plant_id", sa.BigInteger(), nullable=False),
        sa.Column("daily_plan_id", sa.BigInteger(), nullable=False),
        sa.Column("farm_center_id", sa.BigInteger(), nullable=False),
        sa.Column("cage_id", sa.BigInteger(), nullable=False),
        sa.Column("holding_cage_id", sa.BigInteger(), nullable=False),
        sa.Column("shift_id", sa.BigInteger(), nullable=False),
        sa.Column("fish_count", sa.Integer(), nullable=False),
        sa.Column("avg_weight_kg", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        *_audit_columns(),
        sa.Column("row_version", mssql.ROWVERSION(), nullable=False),
        sa.CheckConstraint("avg_weight_kg > 0", name=op.f("ck_harvest_entries_avg_weight_kg")),
        sa.CheckConstraint("fish_count > 0", name=op.f("ck_harvest_entries_fish_count")),
        sa.CheckConstraint("sequence > 0", name=op.f("ck_harvest_entries_sequence")),
        sa.ForeignKeyConstraint(
            ["cage_id"], ["master.cages.id"], name=op.f("fk_harvest_entries_cage_id_cages")
        ),
        sa.ForeignKeyConstraint(
            ["daily_plan_id"],
            ["plan.daily_plans.id"],
            name=op.f("fk_harvest_entries_daily_plan_id_daily_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["farm_center_id"],
            ["master.farm_centers.id"],
            name=op.f("fk_harvest_entries_farm_center_id_farm_centers"),
        ),
        sa.ForeignKeyConstraint(
            ["holding_cage_id"],
            ["master.holding_cages.id"],
            name=op.f("fk_harvest_entries_holding_cage_id_holding_cages"),
        ),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["master.plants.id"], name=op.f("fk_harvest_entries_plant_id_plants")
        ),
        sa.ForeignKeyConstraint(
            ["shift_id"], ["master.shifts.id"], name=op.f("fk_harvest_entries_shift_id_shifts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_harvest_entries")),
        schema="plan",
    )
    op.create_index(
        "ix_harvest_entries_daily_plan_id_sequence",
        "harvest_entries",
        ["daily_plan_id", "sequence"],
        unique=False,
        schema="plan",
    )
    op.create_table(
        "daily_plan_versions",
        sa.Column("plant_id", sa.BigInteger(), nullable=False),
        sa.Column("daily_plan_id", sa.BigInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column(
            "snapshot_at",
            mssql.DATETIME2(precision=6),
            server_default=sa.text("sysutcdatetime()"),
            nullable=False,
        ),
        *_audit_columns(),
        sa.CheckConstraint("kind IN ('publish', 'change')", name=op.f("ck_daily_plan_versions_kind")),
        sa.ForeignKeyConstraint(
            ["daily_plan_id"],
            ["plan.daily_plans.id"],
            name=op.f("fk_daily_plan_versions_daily_plan_id_daily_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["master.plants.id"], name=op.f("fk_daily_plan_versions_plant_id_plants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_plan_versions")),
        sa.UniqueConstraint("daily_plan_id", "number", name="uq_daily_plan_versions_daily_plan_id_number"),
        schema="plan",
    )

    for table in TEMPORAL_TABLES:
        _make_temporal(table)


def downgrade() -> None:
    for table in reversed(TEMPORAL_TABLES):
        _drop_temporal(table)
    op.drop_table("daily_plan_versions", schema="plan")
    op.drop_index("ix_harvest_entries_daily_plan_id_sequence", table_name="harvest_entries", schema="plan")
    op.drop_table("harvest_entries", schema="plan")
    op.drop_table("daily_plans", schema="plan")
    op.execute(f"IF SCHEMA_ID(N'{HISTORY_SCHEMA}') IS NOT NULL EXEC(N'DROP SCHEMA [{HISTORY_SCHEMA}]')")
