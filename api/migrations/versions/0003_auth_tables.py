"""Crea usuarios, roles, permisos, plantas y refresh tokens.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=400), nullable=True),
        sa.Column("module", sa.String(length=50), nullable=False),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False, start=1, increment=1), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
        sa.UniqueConstraint("code", name=op.f("uq_permissions_code")),
        schema="core",
    )
    op.create_table(
        "roles",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=400), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("0"), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("code", name=op.f("uq_roles_code")),
        schema="core",
    )
    op.create_table(
        "users",
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("password_changed_at", mssql.DATETIME2(precision=3), nullable=True),
        sa.Column("failed_login_count", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("locked_at", mssql.DATETIME2(precision=3), nullable=True),
        sa.Column("last_login_at", mssql.DATETIME2(precision=3), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
        schema="core",
    )
    op.create_table(
        "plants",
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("plant_type", sa.String(length=20), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("timezone", sa.String(length=64), server_default="America/Santiago", nullable=False),
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
        sa.CheckConstraint("plant_type IN ('own', 'contract')", name=op.f("ck_plants_plant_type")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plants")),
        sa.UniqueConstraint("code", name=op.f("uq_plants_code")),
        schema="master",
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", mssql.DATETIME2(precision=3), nullable=False),
        sa.Column(
            "created_at",
            mssql.DATETIME2(precision=3),
            server_default=sa.text("sysutcdatetime()"),
            nullable=False,
        ),
        sa.Column("revoked_at", mssql.DATETIME2(precision=3), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False, start=1, increment=1), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["core.users.id"], name=op.f("fk_refresh_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
        schema="core",
    )
    op.create_index(
        op.f("ix_refresh_tokens_family_id"), "refresh_tokens", ["family_id"], unique=False, schema="core"
    )
    op.create_index(
        "ix_refresh_tokens_user_id_revoked_at",
        "refresh_tokens",
        ["user_id", "revoked_at"],
        unique=False,
        schema="core",
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("permission_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            mssql.DATETIME2(precision=3),
            server_default=sa.text("sysutcdatetime()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["core.permissions.id"],
            name=op.f("fk_role_permissions_permission_id_permissions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["core.roles.id"], name=op.f("fk_role_permissions_role_id_roles"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name=op.f("pk_role_permissions")),
        schema="core",
    )
    op.create_table(
        "user_plants",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("plant_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            mssql.DATETIME2(precision=3),
            server_default=sa.text("sysutcdatetime()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["master.plants.id"], name=op.f("fk_user_plants_plant_id_plants")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["core.users.id"], name=op.f("fk_user_plants_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "plant_id", name=op.f("pk_user_plants")),
        schema="core",
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            mssql.DATETIME2(precision=3),
            server_default=sa.text("sysutcdatetime()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["role_id"], ["core.roles.id"], name=op.f("fk_user_roles_role_id_roles")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["core.users.id"], name=op.f("fk_user_roles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", name=op.f("pk_user_roles")),
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("user_roles", schema="core")
    op.drop_table("user_plants", schema="core")
    op.drop_table("role_permissions", schema="core")
    op.drop_index("ix_refresh_tokens_user_id_revoked_at", table_name="refresh_tokens", schema="core")
    op.drop_index(op.f("ix_refresh_tokens_family_id"), table_name="refresh_tokens", schema="core")
    op.drop_table("refresh_tokens", schema="core")
    op.drop_table("plants", schema="master")
    op.drop_table("users", schema="core")
    op.drop_table("roles", schema="core")
    op.drop_table("permissions", schema="core")
