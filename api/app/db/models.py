"""Registro de todos los modelos para Alembic y para las pruebas.

Cada módulo nuevo con tablas debe importarse aquí.
"""

from app.db.base import Base
from app.modules.audit.models import AuditLog
from app.modules.auth.models import RefreshToken
from app.modules.daily_plans.models import DailyPlan, DailyPlanVersion, HarvestEntry
from app.modules.farms.models import Cage, FarmCenter, HoldingCage
from app.modules.jobs.models import Job
from app.modules.parameters.models import Parameter
from app.modules.plants.models import Plant
from app.modules.roles.models import Permission, Role, RolePermission
from app.modules.shifts.models import Shift
from app.modules.users.models import User, UserPlant, UserRole

__all__ = [
    "AuditLog",
    "Base",
    "Cage",
    "DailyPlan",
    "DailyPlanVersion",
    "FarmCenter",
    "HarvestEntry",
    "HoldingCage",
    "Job",
    "Parameter",
    "Permission",
    "Plant",
    "RefreshToken",
    "Role",
    "RolePermission",
    "Shift",
    "User",
    "UserPlant",
    "UserRole",
]
