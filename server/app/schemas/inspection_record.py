from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


InspectionStatus = Literal["good", "warning", "damaged"]
InspectionType = Literal["scheduled", "sudden"]


class InspectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    artifact_id: int
    schedule_id: int | None = None
    previous_image_path: str | None = None
    current_image_path: str | None = None # Cho phép null để tránh lỗi validation khi đang xử lý
    heatmap_path: str | None = None
    damage_score: int = Field(ge=0, le=100)
    ssim_score: str | None = None
    status: InspectionStatus
    inspection_type: InspectionType = "sudden"
    description: str = ""
    detections_json: str | None = None
    created_by: str | None = None
    created_at: datetime


class InspectionListResponse(BaseModel):
    items: list[InspectionRead]
    total: int
