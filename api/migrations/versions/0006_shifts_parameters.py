"""Crea turnos y parámetros; carga el parámetro global de cobertura de turnos.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parameters",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("plant_id", sa.BigInteger(), nullable=True),
        sa.Column("value_type", sa.String(length=10), nullable=False),
        sa.Column("value", sa.String(length=400), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column("description", sa.String(length=400), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
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
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("row_version", mssql.ROWVERSION(), nullable=False),
        sa.CheckConstraint(
            "value_type IN ('int', 'decimal', 'bool', 'text')", name=op.f("ck_parameters_value_type")
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_from < valid_to",
            name=op.f("ck_parameters_validity"),
        ),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["master.plants.id"], name=op.f("fk_parameters_plant_id_plants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parameters")),
        schema="master",
    )
    op.create_index(
        "ix_parameters_key_plant_id", "parameters", ["key", "plant_id"], unique=False, schema="master"
    )
    op.create_table(
        "shifts",
        sa.Column("plant_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("crosses_midnight", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), server_default="0", nullable=False),
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
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("row_version", mssql.ROWVERSION(), nullable=False),
        sa.ForeignKeyConstraint(["plant_id"], ["master.plants.id"], name=op.f("fk_shifts_plant_id_plants")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shifts")),
        sa.UniqueConstraint("plant_id", "name", name="uq_shifts_plant_id_name"),
        schema="master",
    )
    op.create_index(op.f("ix_shifts_plant_id"), "shifts", ["plant_id"], unique=False, schema="master")

    # ADR 0001, decisión 7: por defecto los turnos de una planta pueden dejar huecos en el día.
    parameters = sa.table(
        "parameters",
        sa.column("key", sa.String),
        sa.column("value_type", sa.String),
        sa.column("value", sa.String),
        sa.column("description", sa.String),
        schema="master",
    )
    op.bulk_insert(
        parameters,
        [
            {
                "key": "shifts.full_coverage",
                "value_type": "bool",
                "value": "false",
                "description": "true = los turnos activos de la planta deben cubrir las 24 horas sin huecos.",
            }
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_shifts_plant_id"), table_name="shifts", schema="master")
    op.drop_table("shifts", schema="master")
    op.drop_index("ix_parameters_key_plant_id", table_name="parameters", schema="master")
    op.drop_table("parameters", schema="master")
