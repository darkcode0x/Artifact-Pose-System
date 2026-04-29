from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_container
from app.schemas.devices import (
    DeviceAcksResponse,
    DeviceIdRequest,
    DeviceIdResponse,
    DeviceListResponse,
    DeviceStatusResponse,
    DeviceSummary,
    MoveCommand,
    MoveCommandRequest,
    QueueMoveResponse,
)
from app.services.state import AppContainer

router = APIRouter()


@router.get("/devices", response_model=DeviceListResponse)
def list_devices(
    container: AppContainer = Depends(get_container),
) -> DeviceListResponse:
    entries = container.device_registry.list_all()
    summaries = [
        DeviceSummary(
            device_id=entry["device_id"],
            machine_hash=entry["machine_hash"],
            status=container.command_service.get_status(entry["device_id"]),
        )
        for entry in entries
    ]
    return DeviceListResponse(ok=True, count=len(summaries), devices=summaries)


@router.post("/devices/get_device_id", response_model=DeviceIdResponse)
def get_device_id(
    req: DeviceIdRequest,
    container: AppContainer = Depends(get_container),
) -> DeviceIdResponse:
    try:
        device_id = container.device_registry.allocate_device_id(
            machine_hash=req.machine_hash,
            preferred_device_id=req.preferred_device_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DeviceIdResponse(
        ok=True,
        device_id=device_id,
        machine_hash=req.machine_hash,
    )


@router.post("/devices/{device_id}/queue_move", response_model=QueueMoveResponse)
def queue_move(
    device_id: str,
    cmd: MoveCommand,
    container: AppContainer = Depends(get_container),
) -> QueueMoveResponse:
    payload = cmd.dict()
    if not payload.get("task_id"):
        payload["task_id"] = container.command_service.build_task_id()

    published, publish_result = container.mqtt_bridge.publish_command(device_id, payload)
    queued = 0

    if not published:
        queued = container.command_service.queue_command(device_id, payload)

    return QueueMoveResponse(
        ok=True,
        mode="mqtt" if published else "http_queue_fallback",
        published=published,
        topic=publish_result if published else None,
        publish_error=None if published else publish_result,
        task_id=str(payload["task_id"]),
        queued=queued,
    )


@router.post("/devices/{device_id}/move", response_model=MoveCommand)
def poll_move_command(
    device_id: str,
    req: MoveCommandRequest | None = None,
    container: AppContainer = Depends(get_container),
) -> MoveCommand:
    if req is not None and req.device_id != device_id:
        raise HTTPException(status_code=400, detail="device_id mismatch")

    payload = container.command_service.pop_next_command(device_id)
    return MoveCommand(**payload)


@router.get("/devices/{device_id}/status", response_model=DeviceStatusResponse)
def device_status(
    device_id: str,
    container: AppContainer = Depends(get_container),
) -> DeviceStatusResponse:
    return DeviceStatusResponse(
        ok=True,
        device_id=device_id,
        status=container.command_service.get_status(device_id),
    )


@router.get("/devices/{device_id}/acks", response_model=DeviceAcksResponse)
def device_acks(
    device_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    container: AppContainer = Depends(get_container),
) -> DeviceAcksResponse:
    history = container.command_service.get_acks(device_id, limit=limit)
    return DeviceAcksResponse(
        ok=True,
        device_id=device_id,
        count=len(history),
        acks=history,
    )
