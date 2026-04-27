from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScheduleBase(BaseModel):
    artifact_id: int
    scheduled_date: datetime
    scheduled_time: str = Field(default="09:00", pattern=r"^\d{2}:\d{2}$")
    operator_username: str = Field(default="", max_length=100)
    notes: str = Field(default="", max_length=2000)


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(BaseModel):
    scheduled_date: datetime | None = None
    scheduled_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    operator_username: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)
    completed: bool | None = None


class ScheduleRead(ScheduleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    completed: bool
    created_at: datetime
    artifact_name: str | None = None
