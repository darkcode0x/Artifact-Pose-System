from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.dependencies import get_container
from app.schemas.pose import PoseCorrectionResponse, PoseHealthResponse, PoseInitializeResponse
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
    container: AppContainer = Depends(get_container),
) -> PoseCorrectionResponse:
    temp_dir = container.settings.uploads_dir / "pose"
    image_path = await _save_temp_upload(temp_dir, file)

    try:
        result = container.pose_service.correct_image(image_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PoseCorrectionResponse(ok=True, result=result)


@router.post("/pose/initialize_golden", response_model=PoseInitializeResponse)
async def initialize_golden(
    left_file: UploadFile = File(...),
    right_file: UploadFile = File(...),
    container: AppContainer = Depends(get_container),
) -> PoseInitializeResponse:
    temp_dir = container.settings.uploads_dir / "pose_init"
    left_path = await _save_temp_upload(temp_dir, left_file)
    right_path = await _save_temp_upload(temp_dir, right_file)

    try:
        result = container.pose_service.initialize_golden(left_path, right_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PoseInitializeResponse(
        ok=True,
        message="Golden pose initialized successfully",
        result=result,
    )
