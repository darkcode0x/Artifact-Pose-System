from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List

from app.api.dependencies import get_container
from app.core.database import get_db
from app.models.iot_device import IotDevice, DeviceStatus
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

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])

@router.get("", response_model=List[DeviceSummary])
def list_devices(db: Session = Depends(get_db)):
    devices = db.query(IotDevice).all()
    return [
        DeviceSummary(
            device_id=d.device_id,
            machine_hash=d.device_code,
            status={"db_status": d.status}
        ) for d in devices
    ]

@router.post("", status_code=status.HTTP_201_CREATED)
def create_device(device_code: str, description: str = "", db: Session = Depends(get_db)):
    existing = db.query(IotDevice).filter(IotDevice.device_code == device_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Device code already exists")
    
    new_device = IotDevice(
        device_code=device_code,
        description=description,
        status=DeviceStatus.offline
    )
    db.add(new_device)
    db.commit()
    return {"message": "Device created successfully"}

@router.patch("/{device_id}")
def update_device(device_id: str, description: str | None = None, status: str | None = None, db: Session = Depends(get_db)):
    device = db.query(IotDevice).filter(IotDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if description is not None:
        device.description = description
    if status is not None:
        device.status = DeviceStatus(status.lower())
        
    db.commit()
    return {"message": "Device updated successfully"}

@router.delete("/{device_id}", status_code=204)
def delete_device(device_id: str, db: Session = Depends(get_db)):
    device = db.query(IotDevice).filter(IotDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(device)
    db.commit()

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
