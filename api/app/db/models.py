"""Registro de todos los modelos para Alembic y para las pruebas.

Cada módulo nuevo con tablas debe importarse aquí.
"""

from app.db.base import Base
from app.modules.audit.models import AuditLog
from app.modules.auth.models import RefreshToken
from app.modules.jobs.models import Job
from app.modules.plants.models import Plant
from app.modules.roles.models import Permission, Role, RolePermission
from app.modules.users.models import User, UserPlant, UserRole

__all__ = [
    "AuditLog",
    "Base",
    "Job",
    "Permission",
    "Plant",
    "RefreshToken",
    "Role",
    "RolePermission",
    "User",
    "UserPlant",
    "UserRole",
]
