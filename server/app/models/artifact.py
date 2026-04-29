from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import List

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, 
    Boolean, Enum, Float
)
from sqlalchemy.orm import relationship

from app.core.database import Base

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

class ImageType(str, enum.Enum):
    BASELINE = "baseline"
    INSPECTION = "inspection"

class AlertLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class ComparisonStatus(str, enum.Enum):
    GOOD = "good"
    DAMAGED = "damaged"
    WARNING = "warning"

class InspectionType(str, enum.Enum):
    SCHEDULED = "scheduled"
    SUDDEN = "sudden"

class Artifact(Base):
    __tablename__ = "artifacts"

    artifact_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="good")
    baseline_image_id = Column(
        Integer, 
        ForeignKey("images.image_id", use_alter=True, name="fk_artifact_baseline_image"),
        nullable=True
    )
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)

    # Properties to match Pydantic schemas
    @property
    def id(self) -> int:
        return self.artifact_id

    @property
    def has_image(self) -> bool:
        return self.baseline_image_id is not None

    # Relationships
    images = relationship("Image", foreign_keys="[Image.artifact_id]", back_populates="artifact", cascade="all, delete-orphan")
    comparisons = relationship("ImageComparison", back_populates="artifact", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="artifact", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="artifact", cascade="all, delete-orphan")
    baseline_image = relationship("Image", foreign_keys=[baseline_image_id], post_update=True)

class Image(Base):
    __tablename__ = "images"

    image_id = Column(Integer, primary_key=True, index=True)
    artifact_id = Column(Integer, ForeignKey("artifacts.artifact_id", ondelete="CASCADE"), nullable=False)
    device_id = Column(Integer, ForeignKey("iot_devices.device_id"), nullable=True)
    operator_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    image_type = Column(Enum(ImageType), nullable=False)
    image_path = Column(String(500), nullable=False)
    captured_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    is_valid = Column(Boolean, default=True, nullable=False)

    artifact = relationship("Artifact", foreign_keys=[artifact_id], back_populates="images")
    device = relationship("IotDevice")
    operator = relationship("User")

class ImageComparison(Base):
    __tablename__ = "image_comparisons"

    comparison_id = Column(Integer, primary_key=True, index=True)
    artifact_id = Column(Integer, ForeignKey("artifacts.artifact_id", ondelete="CASCADE"), nullable=False)
    previous_image_id = Column(Integer, ForeignKey("images.image_id"), nullable=False)
    current_image_id = Column(Integer, ForeignKey("images.image_id"), nullable=False)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=True)
    
    damage_score = Column(Float, nullable=False, default=0.0)
    ssim_score = Column(String(16), nullable=True)
    heatmap_path = Column(String(500), nullable=True)
    status = Column(Enum(ComparisonStatus), default=ComparisonStatus.GOOD, nullable=False)
    inspection_type = Column(Enum(InspectionType), default=InspectionType.SUDDEN, nullable=False)
    description = Column(Text, nullable=True)
    detections_json = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    artifact = relationship("Artifact", back_populates="comparisons")
    previous_image = relationship("Image", foreign_keys=[previous_image_id])
    current_image = relationship("Image", foreign_keys=[current_image_id])
    schedule = relationship("Schedule", back_populates="inspection_result")
    alerts = relationship("Alert", back_populates="comparison", cascade="all, delete-orphan")

class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(Integer, primary_key=True, index=True)
    artifact_id = Column(Integer, ForeignKey("artifacts.artifact_id", ondelete="CASCADE"), nullable=False)
    comparison_id = Column(Integer, ForeignKey("image_comparisons.comparison_id", ondelete="CASCADE"), nullable=False)
    alert_level = Column(Enum(AlertLevel), nullable=False)
    is_handled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    artifact = relationship("Artifact", back_populates="alerts")
    comparison = relationship("ImageComparison", back_populates="alerts")

class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    artifact_id = Column(Integer, ForeignKey("artifacts.artifact_id", ondelete="CASCADE"), nullable=False)
    scheduled_date = Column(DateTime(timezone=True), nullable=False)
    scheduled_time = Column(String(8), nullable=False, default="09:00")
    operator_username = Column(String(100), nullable=False, default="")
    notes = Column(Text, nullable=True)
    completed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    artifact = relationship("Artifact", back_populates="schedules")
    inspection_result = relationship("ImageComparison", back_populates="schedule", uselist=False)
