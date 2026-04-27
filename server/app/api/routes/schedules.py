from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.artifact import Artifact, Schedule
from app.schemas.schedule import ScheduleCreate, ScheduleRead, ScheduleUpdate

router = APIRouter(prefix="/api/v1/schedules")


def _serialize(schedule: Schedule) -> ScheduleRead:
    data = ScheduleRead.model_validate(schedule)
    if schedule.artifact is not None:
        data = data.model_copy(update={"artifact_name": schedule.artifact.name})
    return data


@router.get("", response_model=list[ScheduleRead])
def list_schedules(
    date: datetime | None = Query(default=None),
    operator: str | None = None,
    db: Session = Depends(get_db),
) -> list[ScheduleRead]:
    query = db.query(Schedule).order_by(Schedule.scheduled_date.asc())

    if date is not None:
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(hour=23, minute=59, second=59, microsecond=999999)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
            end = end.replace(tzinfo=timezone.utc)
        query = query.filter(
            Schedule.scheduled_date >= start,
            Schedule.scheduled_date <= end,
        )

    if operator:
        query = query.filter(Schedule.operator_username == operator)

    return [_serialize(s) for s in query.all()]


@router.post("", response_model=ScheduleRead, status_code=201)
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
) -> ScheduleRead:
    artifact = db.query(Artifact).filter(Artifact.id == payload.artifact_id).first()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    schedule = Schedule(
        artifact_id=payload.artifact_id,
        scheduled_date=payload.scheduled_date,
        scheduled_time=payload.scheduled_time,
        operator_username=payload.operator_username,
        notes=payload.notes,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return _serialize(schedule)


@router.patch("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
) -> ScheduleRead:
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(schedule, key, value)

    db.commit()
    db.refresh(schedule)
    return _serialize(schedule)


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)) -> None:
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(schedule)
    db.commit()
