from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_container
from app.core.config import get_settings
from app.core.database import get_db
from app.models.artifact import Artifact, Inspection
from app.schemas.artifact import ArtifactCreate, ArtifactRead, ArtifactUpdate
from app.schemas.inspection_record import InspectionListResponse, InspectionRead
from app.services.state import AppContainer

router = APIRouter(prefix="/api/v1/artifacts")


def _to_url(path_str: str | None) -> str | None:
    """Convert an absolute server-side path under uploads_dir to a /uploads/ URL."""
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
    data = ArtifactRead.model_validate(artifact)
    return data.model_copy(update={"reference_image_path": _to_url(artifact.reference_image_path)})


def _serialize_inspection(record: Inspection) -> InspectionRead:
    data = InspectionRead.model_validate(record)
    return data.model_copy(
        update={
            "previous_image_path": _to_url(record.previous_image_path),
            "current_image_path": _to_url(record.current_image_path) or record.current_image_path,
            "heatmap_path": _to_url(record.heatmap_path),
        }
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
    """Artifacts that need attention (warning, need_check, damaged)."""
    artifacts = (
        db.query(Artifact)
        .filter(Artifact.status.in_(["warning", "need_check", "damaged"]))
        .order_by(Artifact.updated_at.desc())
        .all()
    )
    return [_serialize(a) for a in artifacts]


@router.get("/{artifact_id}", response_model=ArtifactRead)
def get_artifact(artifact_id: int, db: Session = Depends(get_db)) -> ArtifactRead:
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return _serialize(artifact)


@router.post("", response_model=ArtifactRead, status_code=201)
def create_artifact(
    payload: ArtifactCreate,
    db: Session = Depends(get_db),
) -> ArtifactRead:
    artifact = Artifact(
        name=payload.name,
        description=payload.description,
        location=payload.location,
        status=payload.status,
        has_image=False,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return _serialize(artifact)


@router.patch("/{artifact_id}", response_model=ArtifactRead)
def update_artifact(
    artifact_id: int,
    payload: ArtifactUpdate,
    db: Session = Depends(get_db),
) -> ArtifactRead:
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(artifact, key, value)

    db.commit()
    db.refresh(artifact)
    return _serialize(artifact)


@router.delete("/{artifact_id}", status_code=204)
def delete_artifact(artifact_id: int, db: Session = Depends(get_db)) -> None:
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
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
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    saved_path = await container.inspection_service.save_reference_image(
        artifact_id=artifact_id,
        file=file,
    )

    artifact.reference_image_path = str(saved_path)
    artifact.has_image = True
    db.commit()
    db.refresh(artifact)
    return _serialize(artifact)


@router.get("/{artifact_id}/inspections", response_model=InspectionListResponse)
def list_artifact_inspections(
    artifact_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> InspectionListResponse:
    if db.query(Artifact).filter(Artifact.id == artifact_id).first() is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    items = (
        db.query(Inspection)
        .filter(Inspection.artifact_id == artifact_id)
        .order_by(Inspection.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    total = (
        db.query(Inspection)
        .filter(Inspection.artifact_id == artifact_id)
        .count()
    )
    return InspectionListResponse(
        items=[_serialize_inspection(item) for item in items],
        total=total,
    )


@router.post("/{artifact_id}/inspect", response_model=InspectionRead)
async def inspect_artifact(
    artifact_id: int,
    file: UploadFile = File(...),
    description: str = Form(default=""),
    created_by: str = Form(default=""),
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
) -> InspectionRead:
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file")

    record = container.inspection_service.run_artifact_inspection(
        db=db,
        artifact=artifact,
        image_bytes=image_bytes,
        original_filename=file.filename or "upload.jpg",
        description=description,
        created_by=created_by or None,
    )
    return _serialize_inspection(record)
