from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


ArtifactStatus = Literal["good", "need_check", "warning", "damaged", "maintenance", "archived"]


class ArtifactBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    location: str = Field(default="", max_length=200)
    status: ArtifactStatus = "good"
    inspection_interval_days: int = Field(default=0, ge=0)


class ArtifactCreate(ArtifactBase):
    # Optional schedule to be created with the artifact
    scheduled_date: datetime | None = None
    scheduled_time: str | None = Field(default="09:00", pattern=r"^\d{2}:\d{2}$")


class ArtifactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=200)
    status: ArtifactStatus | None = None
    inspection_interval_days: int | None = Field(default=None, ge=0)


class ArtifactRead(ArtifactBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    has_image: bool
    reference_image_path: str | None = None
    created_at: datetime
    updated_at: datetime
