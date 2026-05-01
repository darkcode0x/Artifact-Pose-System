from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_container, get_current_user, require_admin
from app.core.database import get_db
from app.models.iot_device import IotDevice, DeviceStatus
from app.models.user import User
from app.schemas.devices import (
    DeviceAcksResponse,
    DeviceIdRequest,
    DeviceIdResponse,
    DeviceStatusResponse,
    DeviceSummary,
    MoveCommand,
    MoveCommandRequest,
    QueueMoveResponse,
)
from app.services.state import AppContainer

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


# --------- DB-backed CRUD ---------

@router.get("", response_model=List[DeviceSummary])
def list_devices(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[DeviceSummary]:
    devices = db.query(IotDevice).order_by(IotDevice.created_at.desc()).all()
    return [
        DeviceSummary(
            device_id=d.device_id,
            machine_hash=d.device_code,
            status={
                "db_status": d.status.value,
                "description": d.description or "",
                "last_active_at": d.last_active_at.isoformat() if d.last_active_at else None,
            },
        )
        for d in devices
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_device(
    device_code: str,
    description: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    existing = db.query(IotDevice).filter(IotDevice.device_code == device_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Device code already exists")

    new_device = IotDevice(
        device_code=device_code,
        description=description,
        status=DeviceStatus.offline,
    )
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    return {"ok": True, "device_id": new_device.device_id, "message": "Device created successfully"}


@router.patch("/{device_id}")
def update_device(
    device_id: str,
    description: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    device = db.query(IotDevice).filter(IotDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if description is not None:
        device.description = description
    if status is not None:
        try:
            device.status = DeviceStatus(status.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    db.commit()
    return {"ok": True, "message": "Device updated successfully"}


@router.delete("/{device_id}", status_code=204)
def delete_device(
    device_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    device = db.query(IotDevice).filter(IotDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(device)
    db.commit()


# --------- IoT operational endpoints (used by Raspberry Pi clients) ---------
# These endpoints don't require auth so devices on the local network can register
# and poll commands. If you want to lock them down, wire in get_current_user.

@router.post("/get_device_id", response_model=DeviceIdResponse)
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


@router.post("/{device_id}/queue_move", response_model=QueueMoveResponse)
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


@router.post("/{device_id}/move", response_model=MoveCommand)
def poll_move_command(
    device_id: str,
    req: MoveCommandRequest | None = None,
    container: AppContainer = Depends(get_container),
) -> MoveCommand:
    if req is not None and req.device_id != device_id:
        raise HTTPException(status_code=400, detail="device_id mismatch")
    payload = container.command_service.pop_next_command(device_id)
    return MoveCommand(**payload)


@router.get("/{device_id}/status", response_model=DeviceStatusResponse)
def device_status(
    device_id: str,
    container: AppContainer = Depends(get_container),
) -> DeviceStatusResponse:
    return DeviceStatusResponse(
        ok=True,
        device_id=device_id,
        status=container.command_service.get_status(device_id),
    )


@router.get("/{device_id}/acks", response_model=DeviceAcksResponse)
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
