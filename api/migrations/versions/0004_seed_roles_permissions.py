"""Carga el catálogo de permisos y los cuatro roles base con su matriz inicial.

La matriz es editable por Admin después; esta migración solo define el punto de partida.
Las fases siguientes agregan sus permisos con migraciones nuevas.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (código, nombre, módulo, descripción)
PERMISSIONS = [
    (
        "users.admin",
        "Administrar usuarios y roles",
        "admin",
        "Crear, editar y desactivar usuarios; restablecer contraseñas; editar roles y su matriz de permisos.",
    ),
    (
        "plants.all",
        "Acceso a todas las plantas",
        "admin",
        "Ve y opera todas las plantas sin asignación explícita.",
    ),
    ("masters.view", "Ver maestros", "masters", "Consultar plantas, turnos y maestros."),
    ("masters.edit", "Editar maestros", "masters", "Crear y editar plantas, turnos y maestros."),
    ("parameters.edit", "Editar parámetros", "masters", "Editar parámetros del sistema y por planta."),
    ("audit.view", "Ver auditoría", "admin", "Consultar el registro de auditoría."),
    ("plan.view", "Ver plan", "plan", "Consultar el plan publicado y su avance."),
    ("plan.edit", "Editar plan", "plan", "Crear y editar el plan diario en borrador o publicado."),
    ("plan.publish", "Publicar plan", "plan", "Publicar el plan diario."),
    ("plan.close", "Cerrar plan", "plan", "Cerrar el plan al terminar la fecha productiva."),
    (
        "production.record",
        "Registrar producción",
        "plan",
        "Registrar observaciones y cumplimiento manual cuando no hay dato en réplica.",
    ),
    ("rules.view", "Ver reglas", "rules", "Consultar matriz de calibrado y reglas de degradación."),
    (
        "rules.edit",
        "Editar reglas",
        "rules",
        "Administrar matriz de calibrado, reglas de degradación y calidades.",
    ),
]

# (código, nombre, descripción)
ROLES = [
    ("planning", "Planificación", "Crea, edita, publica y cierra el plan diario."),
    ("production", "Producción / Frigorífico", "Consulta el plan publicado y registra avance manual."),
    ("quality", "Calidad", "Administra matriz de calibrado, reglas de degradación y calidades."),
    ("admin", "Control de Gestión / Admin", "Administra usuarios, plantas, maestros e integraciones."),
]

# Matriz inicial según la sección 3 de la especificación. Admin recibe todos los permisos.
ROLE_PERMISSIONS = {
    "planning": ["masters.view", "plan.view", "plan.edit", "plan.publish", "plan.close", "rules.view"],
    "production": ["masters.view", "plan.view", "production.record"],
    "quality": ["masters.view", "plan.view", "rules.view", "rules.edit"],
    "admin": [code for code, *_ in PERMISSIONS],
}


def upgrade() -> None:
    permissions = sa.table(
        "permissions",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("module", sa.String),
        sa.column("description", sa.String),
        schema="core",
    )
    roles = sa.table(
        "roles",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("is_system", sa.Boolean),
        schema="core",
    )
    op.bulk_insert(
        permissions,
        [{"code": c, "name": n, "module": m, "description": d} for c, n, m, d in PERMISSIONS],
    )
    op.bulk_insert(roles, [{"code": c, "name": n, "description": d, "is_system": True} for c, n, d in ROLES])
    conn = op.get_bind()
    for role_code, permission_codes in ROLE_PERMISSIONS.items():
        conn.execute(
            sa.text(
                """
                INSERT INTO core.role_permissions (role_id, permission_id)
                SELECT r.id, p.id FROM core.roles r CROSS JOIN core.permissions p
                WHERE r.code = :role AND p.code IN :codes
                """
            ).bindparams(sa.bindparam("codes", expanding=True)),
            {"role": role_code, "codes": permission_codes},
        )


def downgrade() -> None:
    role_codes = [c for c, *_ in ROLES]
    permission_codes = [c for c, *_ in PERMISSIONS]
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE rp FROM core.role_permissions rp JOIN core.roles r ON r.id = rp.role_id WHERE r.code IN :codes"
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": role_codes},
    )
    conn.execute(
        sa.text("DELETE FROM core.roles WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": role_codes},
    )
    conn.execute(
        sa.text("DELETE FROM core.permissions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": permission_codes},
    )
