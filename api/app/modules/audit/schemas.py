from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditEntryOut(BaseModel):
    id: int
    occurred_at: datetime
    user_id: int | None = Field(description="Null = acción del sistema")
    username: str | None
    action: str = Field(examples=["update"])
    entity: str = Field(examples=["master.plants"])
    entity_id: int
    plant_id: int | None
    changes: dict[str, Any] = Field(examples=[{"name": {"old": "Planta VS", "new": "Planta Victoria Sur"}}])
    request_id: str | None
