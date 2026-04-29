from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_container
from app.core.config import get_settings
from app.core.database import get_db
from app.models.artifact import Artifact, Image, ImageComparison, Schedule, InspectionType
from app.schemas.artifact import ArtifactCreate, ArtifactRead, ArtifactUpdate
from app.schemas.inspection_record import InspectionListResponse, InspectionRead
from app.services.state import AppContainer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])


def _to_url(path_str: str | None) -> str | None:
    if not path_str:
        return None
    try:
        uploads_dir = get_settings().uploads_dir.resolve()
        full = Path(path_str).resolve()
        rel = full.relative_to(uploads_dir).as_posix()
        return f"/uploads/{rel}"
    except (ValueError, OSError):
        return path_str


def _serialize(artifact: Artifact) -> ArtifactRead:
    ref_path = artifact.baseline_image.image_path if artifact.baseline_image else None
    return ArtifactRead(
        id=artifact.artifact_id,
        name=artifact.name,
        description=artifact.description or "",
        location=artifact.location or "",
        status=artifact.status,
        has_image=artifact.baseline_image_id is not None,
        reference_image_path=_to_url(ref_path),
        created_at=artifact.created_at,
        updated_at=artifact.updated_at
    )


def _serialize_comparison(record: ImageComparison) -> InspectionRead:
    prev_path = record.previous_image.image_path if record.previous_image else None
    curr_path = record.current_image.image_path if record.current_image else None
    
    return InspectionRead(
        id=record.comparison_id,
        artifact_id=record.artifact_id,
        schedule_id=record.schedule_id,
        previous_image_path=_to_url(prev_path),
        current_image_path=_to_url(curr_path),
        heatmap_path=_to_url(record.heatmap_path),
        damage_score=int(record.damage_score),
        ssim_score=record.ssim_score,
        status=record.status.value,
        inspection_type=record.inspection_type.value,
        description=record.description or "",
        detections_json=record.detections_json,
        created_at=record.created_at,
        created_by=record.created_by,
    )


@router.get("", response_model=list[ArtifactRead])
def list_artifacts(
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[ArtifactRead]:
    query = db.query(Artifact).order_by(Artifact.created_at.desc())
    if status:
        query = query.filter(Artifact.status == status)
    return [_serialize(a) for a in query.all()]


@router.get("/alerts", response_model=list[ArtifactRead])
def list_alerts(db: Session = Depends(get_db)) -> list[ArtifactRead]:
    artifacts = (
        db.query(Artifact)
        .filter(Artifact.status.in_(["warning", "damaged"]))
        .order_by(Artifact.updated_at.desc())
        .all()
    )
    return [_serialize(a) for a in artifacts]


@router.get("/{artifact_id}", response_model=ArtifactRead)
def get_artifact(artifact_id: int, db: Session = Depends(get_db)) -> ArtifactRead:
    artifact = db.query(Artifact).filter(Artifact.artifact_id == artifact_id).first()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return _serialize(artifact)


@router.post("", response_model=ArtifactRead, status_code=201)
def create_artifact(
    payload: ArtifactCreate,
    db: Session = Depends(get_db),
) -> ArtifactRead:
    existing = db.query(Artifact).filter(Artifact.name == payload.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Artifact with name '{payload.name}' already exists."
        )

    artifact = Artifact(
        name=payload.name,
        description=payload.description,
        location=payload.location,
        status=payload.status,
    )
    db.add(artifact)
    db.flush()

    if payload.scheduled_date:
        schedule = Schedule(
            artifact_id=artifact.artifact_id,
            scheduled_date=payload.scheduled_date,
            scheduled_time=payload.scheduled_time or "09:00",
            notes="Initial inspection schedule created with artifact."
        )
        db.add(schedule)

    db.commit()
    db.refresh(artifact)
    return _serialize(artifact)


@router.patch("/{artifact_id}", response_model=ArtifactRead)
def update_artifact(
    artifact_id: int,
    payload: ArtifactUpdate,
    db: Session = Depends(get_db),
) -> ArtifactRead:
    artifact = db.query(Artifact).filter(Artifact.artifact_id == artifact_id).first()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "id": continue
        setattr(artifact, key, value)

    db.commit()
    db.refresh(artifact)
    return _serialize(artifact)


@router.delete("/{artifact_id}", status_code=204)
def delete_artifact(artifact_id: int, db: Session = Depends(get_db)) -> None:
    artifact = db.query(Artifact).filter(Artifact.artifact_id == artifact_id).first()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    db.delete(artifact)
    db.commit()


@router.post("/{artifact_id}/reference", response_model=ArtifactRead)
async def upload_reference_image(
    artifact_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
) -> ArtifactRead:
    artifact = db.query(Artifact).filter(Artifact.artifact_id == artifact_id).first()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    new_image_obj = await container.inspection_service.save_reference_image(
        artifact_id=artifact_id,
        file=file,
    )
    
    db.add(new_image_obj)
    db.flush()

    artifact.baseline_image_id = new_image_obj.image_id
    db.commit()
    db.refresh(artifact)
    return _serialize(artifact)


@router.get("/{artifact_id}/inspections", response_model=InspectionListResponse)
def list_artifact_inspections(
    artifact_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> InspectionListResponse:
    if db.query(Artifact).filter(Artifact.artifact_id == artifact_id).first() is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    items = (
        db.query(ImageComparison)
        .filter(ImageComparison.artifact_id == artifact_id)
        .order_by(ImageComparison.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    total = (
        db.query(ImageComparison)
        .filter(ImageComparison.artifact_id == artifact_id)
        .count()
    )
    return InspectionListResponse(
        items=[_serialize_comparison(item) for item in items],
        total=total,
    )


@router.post("/{artifact_id}/inspect", response_model=InspectionRead)
async def inspect_artifact(
    artifact_id: int,
    file: UploadFile = File(...),
    description: str = Form(default=""),
    created_by: str = Form(default=""),
    inspection_type: str = Form(default="sudden"),
    schedule_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
) -> InspectionRead:
    artifact = db.query(Artifact).filter(Artifact.artifact_id == artifact_id).first()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty image file")

        itype = InspectionType.SCHEDULED if inspection_type == "scheduled" else InspectionType.SUDDEN

        record = container.inspection_service.run_artifact_inspection(
            db=db,
            artifact=artifact,
            image_bytes=image_bytes,
            original_filename=file.filename or "upload.jpg",
            description=description,
            inspection_type=itype,
            schedule_id=schedule_id,
            created_by=created_by or None,
        )
        return _serialize_comparison(record)
    except Exception as e:
        logger.error(f"Inspection failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Analysis failed: {str(e)}"
        )
