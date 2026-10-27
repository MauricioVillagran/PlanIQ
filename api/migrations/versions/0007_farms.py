"""Crea centros, jaulas y jaulas de acopio; agrega el permiso farms.edit.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "farm_centers",
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("zone", sa.String(length=100), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_farm_centers")),
        sa.UniqueConstraint("code", name=op.f("uq_farm_centers_code")),
        schema="master",
    )
    op.create_table(
        "cages",
        sa.Column("farm_center_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["farm_center_id"], ["master.farm_centers.id"], name=op.f("fk_cages_farm_center_id_farm_centers")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cages")),
        sa.UniqueConstraint("farm_center_id", "code", name="uq_cages_farm_center_id_code"),
        schema="master",
    )
    op.create_index(
        op.f("ix_cages_farm_center_id"), "cages", ["farm_center_id"], unique=False, schema="master"
    )
    op.create_table(
        "holding_cages",
        sa.Column("plant_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("capacity_fish", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("capacity_fish > 0", name=op.f("ck_holding_cages_capacity_fish")),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["master.plants.id"], name=op.f("fk_holding_cages_plant_id_plants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_holding_cages")),
        sa.UniqueConstraint("plant_id", "code", name="uq_holding_cages_plant_id_code"),
        schema="master",
    )
    op.create_index(
        op.f("ix_holding_cages_plant_id"), "holding_cages", ["plant_id"], unique=False, schema="master"
    )

    # ADR 0005, decisión 6: Planificación mantiene centros, jaulas y acopios sin depender de Administración.
    op.execute(
        "INSERT INTO core.permissions (code, name, module, description) VALUES "
        "('farms.edit', 'Editar maestros de cultivo', 'masters', "
        "'Crear y editar centros, jaulas y jaulas de acopio.')"
    )
    op.execute(
        "INSERT INTO core.role_permissions (role_id, permission_id) "
        "SELECT r.id, p.id FROM core.roles r CROSS JOIN core.permissions p "
        "WHERE r.code IN ('planning', 'admin') AND p.code = 'farms.edit'"
    )


def downgrade() -> None:
    op.execute(
        "DELETE rp FROM core.role_permissions rp JOIN core.permissions p ON p.id = rp.permission_id "
        "WHERE p.code = 'farms.edit'"
    )
    op.execute("DELETE FROM core.permissions WHERE code = 'farms.edit'")
    op.drop_index(op.f("ix_holding_cages_plant_id"), table_name="holding_cages", schema="master")
    op.drop_table("holding_cages", schema="master")
    op.drop_index(op.f("ix_cages_farm_center_id"), table_name="cages", schema="master")
    op.drop_table("cages", schema="master")
    op.drop_table("farm_centers", schema="master")
