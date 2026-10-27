"""Crea los esquemas core, master, plan, actual e integration.

Revision ID: 0001
Revises:
Create Date: 2026-10-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMAS = ("core", "master", "plan", "actual", "integration")


def upgrade() -> None:
    for schema in SCHEMAS:
        # CREATE SCHEMA debe ser la única instrucción de su lote: se ejecuta con EXEC.
        op.execute(f"IF SCHEMA_ID(N'{schema}') IS NULL EXEC(N'CREATE SCHEMA [{schema}]')")


def downgrade() -> None:
    for schema in reversed(SCHEMAS):
        op.execute(f"IF SCHEMA_ID(N'{schema}') IS NOT NULL EXEC(N'DROP SCHEMA [{schema}]')")
