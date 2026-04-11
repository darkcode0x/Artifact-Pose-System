from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CaptureJobType(str, Enum):
    alignment = "alignment"
    golden_sample = "golden_sample"


class CaptureRequest(BaseModel):
    artifact_id: str = "artifact_demo_001"
    job_type: CaptureJobType = CaptureJobType.alignment
    basename_prefix: str | None = None
    use_latest_metadata: bool = True
    camera_overrides: dict[str, Any] = Field(default_factory=dict)


class StartAlignmentRequest(BaseModel):
    artifact_id: str = "artifact_demo_001"
    use_latest_metadata: bool = True
    camera_overrides: dict[str, Any] = Field(default_factory=dict)


class TriggerCommandResponse(BaseModel):
    ok: bool
    device_id: str
    mode: str
    published: bool
    topic: str | None = None
    publish_error: str | None = None
    task_id: str
    queued: int
    payload: dict[str, Any]


class LatestCaptureMetadataResponse(BaseModel):
    ok: bool
    device_id: str
    metadata: dict[str, Any] | None = None
