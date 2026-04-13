from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.dependencies import get_container
from app.schemas.pose import (
    PoseArtifactListResponse,
    PoseArtifactStatus,
    PoseArtifactStatusResponse,
    PoseCorrectionResponse,
    PoseHealthResponse,
    PoseInitializeResponse,
)
from app.services.state import AppContainer

router = APIRouter()


async def _save_temp_upload(folder: Path, file: UploadFile) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = (file.filename or "upload.png").replace("/", "_").replace("\\", "_")
    target = folder / f"{int(time.time() * 1000)}_{safe_name}"
    target.write_bytes(await file.read())
    return target


@router.get("/pose/health", response_model=PoseHealthResponse)
def pose_health(container: AppContainer = Depends(get_container)) -> PoseHealthResponse:
    return PoseHealthResponse(**container.pose_service.health())


@router.post("/pose/correct", response_model=PoseCorrectionResponse)
async def pose_correct(
    file: UploadFile = File(...),
    artifact_id: str | None = Form(default=None),
    container: AppContainer = Depends(get_container),
) -> PoseCorrectionResponse:
    temp_dir = container.settings.uploads_dir / "pose"
    image_path = await _save_temp_upload(temp_dir, file)

    try:
        result = container.pose_service.correct_image(image_path, artifact_id=artifact_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PoseCorrectionResponse(ok=True, result=result)


@router.post("/pose/initialize_golden", response_model=PoseInitializeResponse)
async def initialize_golden(
    left_file: UploadFile = File(...),
    right_file: UploadFile = File(...),
    artifact_id: str | None = Form(default=None),
    container: AppContainer = Depends(get_container),
) -> PoseInitializeResponse:
    temp_dir = container.settings.uploads_dir / "pose_init"
    left_path = await _save_temp_upload(temp_dir, left_file)
    right_path = await _save_temp_upload(temp_dir, right_file)

    try:
        result = container.pose_service.initialize_golden(
            left_path,
            right_path,
            artifact_id=artifact_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PoseInitializeResponse(
        ok=True,
        message="Golden pose initialized successfully",
        result=result,
    )


@router.post("/pose/initialize_from_sample", response_model=PoseInitializeResponse)
async def initialize_from_sample(
    file: UploadFile = File(...),
    artifact_id: str = Form(...),
    container: AppContainer = Depends(get_container),
) -> PoseInitializeResponse:
    temp_dir = container.settings.uploads_dir / "pose_sample"
    image_path = await _save_temp_upload(temp_dir, file)

    try:
        result = container.pose_service.initialize_from_sample(image_path, artifact_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PoseInitializeResponse(
        ok=True,
        message="Golden sample initialized successfully",
        result=result,
    )


@router.get("/pose/artifacts", response_model=PoseArtifactListResponse)
def list_pose_artifacts(container: AppContainer = Depends(get_container)) -> PoseArtifactListResponse:
    artifacts = [PoseArtifactStatus(**item) for item in container.pose_service.list_artifacts()]
    return PoseArtifactListResponse(ok=True, artifacts=artifacts)


@router.get("/pose/artifacts/{artifact_id}", response_model=PoseArtifactStatusResponse)
def pose_artifact_status(
    artifact_id: str,
    container: AppContainer = Depends(get_container),
) -> PoseArtifactStatusResponse:
    status = PoseArtifactStatus(**container.pose_service.artifact_status(artifact_id))
    return PoseArtifactStatusResponse(ok=True, artifact=status)
