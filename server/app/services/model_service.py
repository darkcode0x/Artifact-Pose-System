from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
import zipfile

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


class TorchRuntimeModel(BaseRuntimeModel):
    def __init__(self, model_path: Path) -> None:
        try:
            import torch
        except Exception as exc:
            raise RuntimeError(
                "Can not import torch. Install it with: pip install torch"
            ) from exc

        self._torch = torch
        self._model = self._load_model(model_path)
        self._model.eval()

    def _load_model(self, model_path: Path) -> Any:
        jit_error: Exception | None = None

        try:
            return self._torch.jit.load(str(model_path), map_location="cpu")
        except Exception as exc:
            jit_error = exc

        try:
            raw_model = self._torch.load(str(model_path), map_location="cpu")
        except Exception as exc:
            raise RuntimeError(
                "Can not load torch model. "
                f"jit_error={jit_error}; torch_load_error={exc}"
            ) from exc

        if hasattr(raw_model, "eval") and callable(getattr(raw_model, "forward", None)):
            return raw_model

        if isinstance(raw_model, dict):
            for key in ("ema", "model", "module", "net", "network"):
                candidate = raw_model.get(key)
                if hasattr(candidate, "eval") and callable(getattr(candidate, "forward", None)):
                    return candidate

        raise RuntimeError(
            "Can not extract callable torch model from checkpoint. "
            "Expected torch module or one of keys: ema/model/module/net/network"
        )

    def predict(self, input_data: Any) -> Any:
        tensor = self._torch.tensor(input_data, dtype=self._torch.float32)
        if tensor.ndim == 1:
            tensor = tensor.unsqueeze(0)

        with self._torch.no_grad():
            output = self._model(tensor)

        if hasattr(output, "detach"):
            output = output.detach().cpu().numpy()
        return _to_jsonable(output)


class UltralyticsRuntimeModel(BaseRuntimeModel):
    def __init__(self, model_path: Path) -> None:
        try:
            from ultralytics import YOLO
        except Exception as exc:
            raise RuntimeError(
                "Can not import ultralytics. Install it with: pip install ultralytics"
            ) from exc

        self._model = YOLO(str(model_path))

    def predict(self, input_data: Any) -> Any:
        source, kwargs = self._resolve_source_and_kwargs(input_data)
        results = self._model.predict(source=source, verbose=False, **kwargs)

        packed: list[dict[str, Any]] = []
        for result in results:
            names = getattr(result, "names", {}) or {}
            boxes_payload: list[dict[str, Any]] = []

            boxes = getattr(result, "boxes", None)
            if boxes is not None:
                xyxy = boxes.xyxy.tolist() if hasattr(boxes, "xyxy") else []
                conf = boxes.conf.tolist() if hasattr(boxes, "conf") else []
                cls = boxes.cls.tolist() if hasattr(boxes, "cls") else []

                for idx, coords in enumerate(xyxy):
                    class_id = int(cls[idx]) if idx < len(cls) else -1
                    class_name = names.get(class_id, str(class_id)) if isinstance(names, dict) else str(class_id)
                    confidence = float(conf[idx]) if idx < len(conf) else None

                    boxes_payload.append(
                        {
                            "xyxy": [float(v) for v in coords],
                            "class_id": class_id,
                            "class_name": class_name,
                            "confidence": confidence,
                        }
                    )

            packed.append(
                {
                    "path": str(getattr(result, "path", "")),
                    "orig_shape": list(getattr(result, "orig_shape", [])) if getattr(result, "orig_shape", None) else None,
                    "boxes": boxes_payload,
                }
            )

        return packed

    @staticmethod
    def _resolve_source_and_kwargs(input_data: Any) -> tuple[Any, dict[str, Any]]:
        if isinstance(input_data, dict):
            source = (
                input_data.get("source")
                or input_data.get("image_path")
                or input_data.get("path")
            )
            if source is None:
                raise ValueError("Ultralytics input requires one of: source, image_path, path")

            kwargs: dict[str, Any] = {}
            for key in ("conf", "iou", "imgsz", "device", "max_det", "agnostic_nms"):
                if key in input_data:
                    kwargs[key] = input_data[key]
            return source, kwargs

        if isinstance(input_data, (str, Path, list, tuple)):
            return input_data, {}

        raise ValueError(
            "Ultralytics input must be image source (path/url/list) "
            "or dict with source/image_path/path"
        )


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
        self._last_sync_report: dict[str, Any] | None = None
        self._lock = Lock()

    def list_models(self) -> list[LoadedModel]:
        with self._lock:
            return list(self._models.values())

    def get_default_model_name(self) -> str | None:
        with self._lock:
            if not self._models:
                return None
            return next(iter(self._models.keys()))

    def sync_from_model_dir(self, force_reload: bool = False) -> dict[str, Any]:
        supported_extensions = {".onnx", ".pt", ".pth"}
        model_dir = self._settings.model_dir

        candidates = sorted(
            [
                path
                for path in model_dir.glob("*")
                if path.is_file() and path.suffix.lower() in supported_extensions
            ],
            key=lambda item: item.name.lower(),
        )

        loaded: list[dict[str, Any]] = []
        skipped: list[str] = []
        failed: list[dict[str, str]] = []

        for model_path in candidates:
            model_name = model_path.stem

            with self._lock:
                existing = self._models.get(model_name)

            if existing and not force_reload and existing.path == str(model_path):
                skipped.append(model_name)
                continue

            try:
                model = self.load_model(
                    name=model_name,
                    path=str(model_path),
                    backend="auto",
                    labels=[],
                )
                loaded.append(
                    {
                        "name": model.name,
                        "backend": model.backend,
                        "path": model.path,
                        "labels": model.labels,
                        "loaded_at": model.loaded_at,
                    }
                )
            except Exception as exc:
                failed.append(
                    {
                        "name": model_name,
                        "path": str(model_path),
                        "error": str(exc),
                    }
                )

        report = {
            "ok": True,
            "model_dir": str(model_dir),
            "total_files": len(candidates),
            "loaded_count": len(loaded),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
            "loaded": loaded,
            "skipped": skipped,
            "failed": failed,
        }

        with self._lock:
            self._last_sync_report = report

        return report

    def last_sync_report(self) -> dict[str, Any] | None:
        with self._lock:
            return self._last_sync_report

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
            if ModelService._looks_like_ultralytics_checkpoint(model_path):
                return "ultralytics"
            return "torch"

        raise ValueError(
            "Can not detect backend from model extension. "
            "Use .onnx, .pt, or .pth, or set backend explicitly."
        )

    @staticmethod
    def _looks_like_ultralytics_checkpoint(model_path: Path) -> bool:
        try:
            if not zipfile.is_zipfile(model_path):
                return False

            with zipfile.ZipFile(model_path) as archive:
                pkl_name = next(
                    (name for name in archive.namelist() if name.endswith("data.pkl")),
                    None,
                )
                if pkl_name is None:
                    return False

                payload = archive.read(pkl_name)
                return b"ultralytics." in payload
        except Exception:
            return False

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
            return TorchRuntimeModel(model_path)

        if backend == "ultralytics":
            return UltralyticsRuntimeModel(model_path)

        raise ValueError(f"Unsupported backend: {backend}")
