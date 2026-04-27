from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


InspectionStatus = Literal["good", "warning", "damaged"]


class InspectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    artifact_id: int
    previous_image_path: str | None = None
    current_image_path: str
    heatmap_path: str | None = None
    damage_score: int = Field(ge=0, le=100)
    ssim_score: str | None = None
    status: InspectionStatus
    description: str = ""
    detections_json: str | None = None
    created_by: str | None = None
    created_at: datetime


class InspectionListResponse(BaseModel):
    items: list[InspectionRead]
    total: int
