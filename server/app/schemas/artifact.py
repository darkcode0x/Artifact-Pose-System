from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


ArtifactStatus = Literal["good", "need_check", "warning", "damaged", "maintenance"]


class ArtifactBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    location: str = Field(default="", max_length=200)
    status: ArtifactStatus = "good"


class ArtifactCreate(ArtifactBase):
    pass


class ArtifactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=200)
    status: ArtifactStatus | None = None


class ArtifactRead(ArtifactBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    has_image: bool
    reference_image_path: str | None = None
    created_at: datetime
    updated_at: datetime
