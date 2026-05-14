from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DeviceIdRequest(BaseModel):
    machine_hash: str = Field(min_length=1)
    preferred_device_id: str | None = None


class DeviceIdResponse(BaseModel):
    ok: bool
    device_id: str
    machine_hash: str


class MoveCommandRequest(BaseModel):
    device_id: str


class MoveCommand(BaseModel):
    action: str
    task_id: str | None = None
    direction: str = "none"
    angle: float = 0.0
    step: int = 0
    yaw_deg: float | None = None
    pitch_deg: float | None = None
    yaw_delta: float = 0.0
    pitch_delta: float = 0.0
    x_steps: int = 0
    z_steps: int = 0
    x_dir: int = 1
    z_dir: int = 1
    artifact_id: str | None = None
    basename: str | None = None
    capture_job: str | None = None
    autofocus_mode: str | None = None
    lens_position: float | None = None
    awbgains: list[float] | tuple[float, float] | None = None
    gain: float | None = None
    shutter: int | None = None
    pre_set_controls_delay_sec: float | None = None
    pre_capture_request_delay_sec: float | None = None
    autofocus_probe_sec: float | None = None
    movement_steps: list[dict[str, Any]] | None = None
    capture_after_move: dict[str, Any] | bool | None = None
    workflow: dict[str, Any] | None = None


class QueueMoveResponse(BaseModel):
    ok: bool
    mode: str
    published: bool
    topic: str | None = None
    publish_error: str | None = None
    task_id: str
    queued: int


class DeviceStatusResponse(BaseModel):
    ok: bool
    device_id: str
    status: dict[str, Any] | None = None


class DeviceAcksResponse(BaseModel):
    ok: bool
    device_id: str
    count: int
    acks: list[dict[str, Any]]


class DeviceSummary(BaseModel):
    device_id: str
    machine_hash: str
    status: dict[str, Any] | None = None


class DeviceListResponse(BaseModel):
    ok: bool
    count: int
    devices: list[DeviceSummary]
