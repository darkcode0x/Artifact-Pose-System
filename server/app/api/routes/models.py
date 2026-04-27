from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.dependencies import get_container
from app.schemas.models import (
    ModelDetectResponse,
    ModelInfo,
    ModelLoadRequest,
    ModelLoadResponse,
    ModelPredictRequest,
    ModelPredictResponse,
)
from app.services.state import AppContainer

router = APIRouter()


@router.get("/models", response_model=list[ModelInfo])
def list_models(container: AppContainer = Depends(get_container)) -> list[ModelInfo]:
    models = container.model_service.list_models()
    return [
        ModelInfo(
            name=item.name,
            backend=item.backend,
            path=item.path,
            labels=item.labels,
            loaded_at=item.loaded_at,
        )
        for item in models
    ]


@router.post("/models/load", response_model=ModelLoadResponse)
def load_model(
    req: ModelLoadRequest,
    container: AppContainer = Depends(get_container),
) -> ModelLoadResponse:
    try:
        loaded = container.model_service.load_model(
            name=req.name,
            path=req.path,
            backend=req.backend,
            labels=req.labels,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ModelLoadResponse(
        ok=True,
        model=ModelInfo(
            name=loaded.name,
            backend=loaded.backend,
            path=loaded.path,
            labels=loaded.labels,
            loaded_at=loaded.loaded_at,
        ),
    )


@router.delete("/models/{name}")
def unload_model(
    name: str,
    container: AppContainer = Depends(get_container),
) -> dict[str, bool]:
    removed = container.model_service.unload_model(name)
    return {"ok": removed}


@router.post("/models/{name}/predict", response_model=ModelPredictResponse)
def predict(
    name: str,
    req: ModelPredictRequest,
    container: AppContainer = Depends(get_container),
) -> ModelPredictResponse:
    try:
        output = container.model_service.predict(name, req.input_data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ModelPredictResponse(
        ok=True,
        model_name=name,
        output=output,
    )


@router.post("/models/{name}/detect", response_model=ModelDetectResponse)
async def detect_image(
    name: str,
    file: UploadFile = File(...),
    container: AppContainer = Depends(get_container),
) -> ModelDetectResponse:
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file")

    try:
        output = container.model_service.detect_image(name, image_bytes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ModelDetectResponse(
        ok=True,
        model_name=name,
        output=output,
    )
