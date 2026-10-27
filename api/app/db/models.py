"""Registro de todos los modelos para Alembic y para las pruebas.

Cada módulo nuevo con tablas debe importarse aquí.
"""

from app.db.base import Base
from app.modules.jobs.models import Job

__all__ = ["Base", "Job"]
