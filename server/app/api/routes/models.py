from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_container
from app.schemas.models import (
    ModelInfo,
    ModelLoadRequest,
    ModelLoadResponse,
    ModelPredictRequest,
    ModelPredictResponse,
    ModelSyncFailure,
    ModelSyncResponse,
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


@router.post("/models/sync", response_model=ModelSyncResponse)
def sync_models(
    force_reload: bool = False,
    container: AppContainer = Depends(get_container),
) -> ModelSyncResponse:
    report = container.model_service.sync_from_model_dir(force_reload=force_reload)

    loaded_items = [
        ModelInfo(
            name=item["name"],
            backend=item["backend"],
            path=item.get("path"),
            labels=item.get("labels", []),
            loaded_at=item["loaded_at"],
        )
        for item in report.get("loaded", [])
    ]

    failed_items = [
        ModelSyncFailure(
            name=item["name"],
            path=item["path"],
            error=item["error"],
        )
        for item in report.get("failed", [])
    ]

    return ModelSyncResponse(
        ok=True,
        model_dir=report.get("model_dir", ""),
        total_files=int(report.get("total_files", 0)),
        loaded_count=int(report.get("loaded_count", 0)),
        skipped_count=int(report.get("skipped_count", 0)),
        failed_count=int(report.get("failed_count", 0)),
        loaded=loaded_items,
        skipped=list(report.get("skipped", [])),
        failed=failed_items,
    )
