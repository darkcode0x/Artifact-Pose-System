from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np

from app.core.config import Settings


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.generic,)):
        return value.item()
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


class BaseRuntimeModel:
    def predict(self, input_data: Any) -> Any:
        raise NotImplementedError


class OnnxRuntimeModel(BaseRuntimeModel):
    def __init__(self, model_path: Path) -> None:
        try:
            import onnxruntime as ort
        except Exception as exc:
            raise RuntimeError(
                "Can not import onnxruntime. Install it with: pip install onnxruntime"
            ) from exc

        self._session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self._input_names = [inp.name for inp in self._session.get_inputs()]
        if not self._input_names:
            raise RuntimeError("ONNX model has no input tensor")

    def predict(self, input_data: Any) -> Any:
        arr = np.asarray(input_data, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)

        output = self._session.run(None, {self._input_names[0]: arr})
        return _to_jsonable(output)


class TorchScriptRuntimeModel(BaseRuntimeModel):
    def __init__(self, model_path: Path) -> None:
        try:
            import torch
        except Exception as exc:
            raise RuntimeError(
                "Can not import torch. Install it with: pip install torch"
            ) from exc

        self._torch = torch
        self._model = torch.jit.load(str(model_path), map_location="cpu")
        self._model.eval()

    def predict(self, input_data: Any) -> Any:
        tensor = self._torch.tensor(input_data, dtype=self._torch.float32)
        if tensor.ndim == 1:
            tensor = tensor.unsqueeze(0)

        with self._torch.no_grad():
            output = self._model(tensor)

        if hasattr(output, "detach"):
            output = output.detach().cpu().numpy()
        return _to_jsonable(output)


@dataclass
class LoadedModel:
    name: str
    backend: str
    path: str | None
    labels: list[str]
    loaded_at: str
    runtime_model: BaseRuntimeModel


class ModelService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._models: dict[str, LoadedModel] = {}
        self._lock = Lock()

    def list_models(self) -> list[LoadedModel]:
        with self._lock:
            return list(self._models.values())

    def load_model(
        self,
        name: str,
        path: str | None,
        backend: str,
        labels: list[str] | None = None,
    ) -> LoadedModel:
        runtime_backend = backend.lower().strip() or "auto"
        model_path: Path | None = None

        if path:
            candidate = Path(path)
            if not candidate.is_absolute():
                candidate = self._settings.model_dir / candidate
            model_path = candidate

        if runtime_backend == "auto":
            runtime_backend = self._detect_backend(model_path)

        runtime_model = self._build_runtime_model(runtime_backend, model_path)

        loaded = LoadedModel(
            name=name,
            backend=runtime_backend,
            path=str(model_path) if model_path else None,
            labels=labels or [],
            loaded_at=_utc_now_iso(),
            runtime_model=runtime_model,
        )

        with self._lock:
            self._models[name] = loaded

        return loaded

    def unload_model(self, name: str) -> bool:
        with self._lock:
            return self._models.pop(name, None) is not None

    def predict(self, name: str, input_data: Any) -> Any:
        with self._lock:
            loaded = self._models.get(name)

        if loaded is None:
            raise KeyError(f"Model '{name}' is not loaded")

        result = loaded.runtime_model.predict(input_data)
        return _to_jsonable(result)

    @staticmethod
    def _detect_backend(model_path: Path | None) -> str:
        if model_path is None:
            raise ValueError("Model path is required when backend is 'auto'")

        suffix = model_path.suffix.lower()
        if suffix == ".onnx":
            return "onnx"
        if suffix in {".pt", ".pth"}:
            return "torchscript"

        raise ValueError(
            "Can not detect backend from model extension. "
            "Use .onnx, .pt, or .pth, or set backend explicitly."
        )

    def _build_runtime_model(
        self,
        backend: str,
        model_path: Path | None,
    ) -> BaseRuntimeModel:
        if model_path is None:
            raise ValueError("Model path is required for backend '%s'" % backend)

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        if backend == "onnx":
            return OnnxRuntimeModel(model_path)

        if backend in {"torch", "torchscript"}:
            return TorchScriptRuntimeModel(model_path)

        raise ValueError(f"Unsupported backend: {backend}")
