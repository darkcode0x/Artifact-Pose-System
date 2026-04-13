from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelLoadRequest(BaseModel):
    name: str = Field(min_length=1)
    path: str | None = None
    backend: str = "auto"
    labels: list[str] = Field(default_factory=list)


class ModelInfo(BaseModel):
    name: str
    backend: str
    path: str | None = None
    labels: list[str] = Field(default_factory=list)
    loaded_at: str


class ModelLoadResponse(BaseModel):
    ok: bool
    model: ModelInfo


class ModelPredictRequest(BaseModel):
    input_data: Any


class ModelPredictResponse(BaseModel):
    ok: bool
    model_name: str
    output: Any


class ModelSyncFailure(BaseModel):
    name: str
    path: str
    error: str


class ModelSyncResponse(BaseModel):
    ok: bool
    model_dir: str
    total_files: int
    loaded_count: int
    skipped_count: int
    failed_count: int
    loaded: list[ModelInfo] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    failed: list[ModelSyncFailure] = Field(default_factory=list)
