from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InspectionMetadata(BaseModel):
    device_id: str
    artifact_id: str
    calibration_data: dict[str, Any] = Field(default_factory=dict)
    model_name: str | None = None
    ai_input: dict[str, Any] | None = None


class InspectionUploadResponse(BaseModel):
    ok: bool
    message: str
    saved_file: str
    size_bytes: int
    pose_result: dict[str, Any] | None = None
    correction_dispatch: dict[str, Any] | None = None
    ai_result: dict[str, Any] | None = None
