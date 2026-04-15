from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_container
from app.schemas.workflow import (
    CaptureRequest,
    LatestCaptureMetadataResponse,
    StartAlignmentRequest,
    StartInitializationRequest,
    TriggerCommandResponse,
)
from app.services.state import AppContainer

router = APIRouter()


def _extract_lens_from_metadata(latest_metadata: dict[str, Any]) -> float | None:
    runtime = latest_metadata.get("camera_runtime_metadata")
    static = latest_metadata.get("camera_static_params")
    if not isinstance(runtime, dict):
        runtime = {}
    if not isinstance(static, dict):
        static = {}

    for value in (
        runtime.get("autofocus_lens_position"),
        runtime.get("applied_lens_position"),
        static.get("lens_position"),
    ):
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue

    return None


def _build_capture_payload(
    *,
    container: AppContainer,
    device_id: str,
    artifact_id: str,
    capture_job: str,
    basename_prefix: str,
    use_latest_metadata: bool,
    camera_overrides: dict[str, Any],
    workflow: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "action": "capture",
        "task_id": container.command_service.build_task_id(),
        "artifact_id": artifact_id,
        "capture_job": capture_job,
        "basename": f"{basename_prefix}_{artifact_id}_{int(time.time() * 1000)}",
        "workflow": workflow,
    }

    if use_latest_metadata:
        latest = container.command_service.get_latest_capture_metadata(device_id)
        if isinstance(latest, dict):
            static = latest.get("camera_static_params")
            if isinstance(static, dict):
                for key in (
                    "autofocus_mode",
                    "awbgains",
                    "gain",
                    "shutter",
                    "pre_set_controls_delay_sec",
                    "pre_capture_request_delay_sec",
                    "autofocus_probe_sec",
                ):
                    if key in static:
                        payload[key] = static[key]

            lens_position = _extract_lens_from_metadata(latest)
            if lens_position is not None:
                payload["lens_position"] = lens_position

    if isinstance(camera_overrides, dict):
        for key, value in camera_overrides.items():
            payload[key] = value

    return payload


def _publish_or_queue(
    container: AppContainer,
    device_id: str,
    payload: dict[str, Any],
) -> TriggerCommandResponse:
    published, result = container.mqtt_bridge.publish_command(device_id, payload)
    queued = 0
    mode = "mqtt"

    if not published:
        queued = container.command_service.queue_command(device_id, payload)
        mode = "http_queue_fallback"

    return TriggerCommandResponse(
        ok=True,
        device_id=device_id,
        mode=mode,
        published=published,
        topic=result if published else None,
        publish_error=None if published else result,
        task_id=str(payload["task_id"]),
        queued=queued,
        payload=payload,
    )


@router.post("/workflows/{device_id}/capture-request", response_model=TriggerCommandResponse)
def capture_request(
    device_id: str,
    req: CaptureRequest,
    container: AppContainer = Depends(get_container),
) -> TriggerCommandResponse:
    capture_job = req.job_type.value
    basename_prefix = req.basename_prefix or (
        "golden_sample" if capture_job == "golden_sample" else "align_capture"
    )

    payload = _build_capture_payload(
        container=container,
        device_id=device_id,
        artifact_id=req.artifact_id,
        capture_job=capture_job,
        basename_prefix=basename_prefix,
        use_latest_metadata=req.use_latest_metadata,
        camera_overrides=req.camera_overrides,
        workflow={
            "request_type": "capture_request",
            "capture_job": capture_job,
            "auto_alignment_loop": False,
        },
    )
    return _publish_or_queue(container, device_id, payload)


@router.post("/workflows/{device_id}/start-alignment", response_model=TriggerCommandResponse)
def start_alignment(
    device_id: str,
    req: StartAlignmentRequest,
    container: AppContainer = Depends(get_container),
) -> TriggerCommandResponse:
    payload = _build_capture_payload(
        container=container,
        device_id=device_id,
        artifact_id=req.artifact_id,
        capture_job="alignment",
        basename_prefix="align_start",
        use_latest_metadata=req.use_latest_metadata,
        camera_overrides=req.camera_overrides,
        workflow={
            "request_type": "start_alignment",
            "capture_job": "alignment",
            "auto_alignment_loop": True,
        },
    )
    container.inspection_service.reset_alignment_counter(device_id, req.artifact_id)
    return _publish_or_queue(container, device_id, payload)


@router.post("/workflows/{device_id}/start-initialization", response_model=TriggerCommandResponse)
def start_initialization(
    device_id: str,
    req: StartInitializationRequest,
    container: AppContainer = Depends(get_container),
) -> TriggerCommandResponse:
    baseline_steps = int(round(req.baseline_mm * req.steps_per_mm))

    payload: dict[str, Any] = {
        "action": "capture_stereo_pair",
        "task_id": container.command_service.build_task_id(),
        "artifact_id": req.artifact_id,
        "baseline_steps": baseline_steps,
        "baseline_mm": req.baseline_mm,
        "steps_per_mm": req.steps_per_mm,
        "workflow": {
            "request_type": "start_initialization",
            "capture_job": "golden_sample",
        },
    }

    if isinstance(req.camera_overrides, dict):
        for key, value in req.camera_overrides.items():
            payload[key] = value

    return _publish_or_queue(container, device_id, payload)


@router.get(
    "/workflows/{device_id}/latest-capture-metadata",
    response_model=LatestCaptureMetadataResponse,
)
def latest_capture_metadata(
    device_id: str,
    container: AppContainer = Depends(get_container),
) -> LatestCaptureMetadataResponse:
    metadata = container.command_service.get_latest_capture_metadata(device_id)
    return LatestCaptureMetadataResponse(ok=True, device_id=device_id, metadata=metadata)
