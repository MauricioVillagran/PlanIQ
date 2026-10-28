from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plant_id: int
    title: str = Field(examples=["Plan del 28-10-2026 publicado"])
    body: str | None
    link: str | None = Field(examples=["/plan?plant=1&date=2026-10-28"])
    read_at: datetime | None
    created_at: datetime


class NotificationSummaryOut(BaseModel):
    unread: int
    poll_seconds: int = Field(description="Cada cuánto consultar (parámetro notifications.poll_seconds)")


class ReadAllOut(BaseModel):
    updated: int
