from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class PoseHealthResponse(BaseModel):
    ok: bool
    available: bool
    artifact_pose_root: str
    camera_params_dir: str
    camera_params: str
    configured_lens_position: Optional[float]
    camera_lens_position: Optional[float]
    golden_pose: str
    message: str


class PoseCorrectionResponse(BaseModel):
    ok: bool
    result: dict


class PoseInitializeResponse(BaseModel):
    ok: bool
    message: str
    result: dict
