from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=False, default="")
    location = Column(String(200), nullable=False, default="")
    status = Column(String(32), nullable=False, default="good", index=True)
    has_image = Column(Boolean, nullable=False, default=False)
    reference_image_path = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
    )

    inspections = relationship(
        "Inspection",
        back_populates="artifact",
        cascade="all, delete-orphan",
        order_by="Inspection.created_at.desc()",
    )
    schedules = relationship(
        "Schedule",
        back_populates="artifact",
        cascade="all, delete-orphan",
    )


class Inspection(Base):
    __tablename__ = "inspections"

    id = Column(Integer, primary_key=True, index=True)
    artifact_id = Column(
        Integer,
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_image_path = Column(String(500), nullable=True)
    current_image_path = Column(String(500), nullable=False)
    heatmap_path = Column(String(500), nullable=True)
    damage_score = Column(Integer, nullable=False, default=0)
    ssim_score = Column(String(16), nullable=True)
    status = Column(String(32), nullable=False, default="good")
    description = Column(Text, nullable=False, default="")
    detections_json = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now, index=True)

    artifact = relationship("Artifact", back_populates="inspections")


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    artifact_id = Column(
        Integer,
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheduled_date = Column(DateTime(timezone=True), nullable=False, index=True)
    scheduled_time = Column(String(8), nullable=False, default="09:00")
    operator_username = Column(String(100), nullable=False, default="")
    notes = Column(Text, nullable=False, default="")
    completed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    artifact = relationship("Artifact", back_populates="schedules")
