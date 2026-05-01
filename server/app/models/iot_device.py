from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Enum
from app.core.database import Base

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

class DeviceStatus(str, enum.Enum):
    online = "online"
    offline = "offline"

class IotDevice(Base):
    __tablename__ = "iot_devices"

    device_id = Column(String(6), primary_key=True, index=True)
    device_code = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(DeviceStatus, name="device_status"), default=DeviceStatus.offline, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    last_active_at = Column(DateTime(timezone=True), nullable=True)
