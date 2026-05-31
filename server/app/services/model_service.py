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


class UltralyticsYoloRuntimeModel(BaseRuntimeModel):
    def __init__(self, model_path: Path, imgsz: int = 960) -> None:
        try:
            from ultralytics import YOLO
        except Exception as exc:
            raise RuntimeError(
                "Can not import ultralytics. Install it with: pip install ultralytics"
            ) from exc

        self._model = YOLO(str(model_path))
        self._imgsz = imgsz
        self._names: dict[int, str] = dict(self._model.names) if hasattr(self._model, "names") else {}

    @property
    def names(self) -> dict[int, str]:
        return self._names

    def predict(self, input_data: Any) -> Any:
        image = self._decode_image(input_data)
        results = self._model.predict(
            image,
            imgsz=self._imgsz,
            conf=0.15,
            iou=0.5,
            verbose=False,
        )
        return self._results_to_json(results)

    @staticmethod
    def _decode_image(input_data: Any) -> np.ndarray:
        import cv2

        if isinstance(input_data, (bytes, bytearray)):
            buffer = np.frombuffer(input_data, dtype=np.uint8)
            image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Invalid image bytes")
            return image

        if isinstance(input_data, str):
            image = cv2.imread(input_data)
            if image is None:
                raise ValueError(f"Can not read image at path: {input_data}")
            return image

        array = np.asarray(input_data)
        if array.ndim not in (2, 3):
            raise ValueError("Image array must be 2D or 3D")
        return array

    def _results_to_json(self, results: Any) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None or boxes.xyxy is None or len(boxes) == 0:
                output.append({"detections": []})
                continue

            xyxy = boxes.xyxy.cpu().numpy().tolist()
            conf = boxes.conf.cpu().numpy().tolist()
            cls = boxes.cls.cpu().numpy().astype(int).tolist()

            detections = []
            for i, class_id in enumerate(cls):
                x1, y1, x2, y2 = xyxy[i]
                detections.append(
                    {
                        "class_id": int(class_id),
                        "class_name": self._names.get(int(class_id), str(int(class_id))),
                        "confidence": float(conf[i]),
                        "bbox_xyxy": [float(x1), float(y1), float(x2), float(y2)],
                    }
                )
            output.append({"detections": detections})
        return output

    def predict_crops_batch(
        self,
        crop_list: list,  # [(crop_arr_np, ox, oy, spec_label, r_ssim), ...]
        conf: float = 0.15,
        sub_batch: int = 4,
    ) -> list[dict]:
        """Run YOLO on crop list in sub-batches. Returns dets projected to full-image coords."""
        import cv2
        import numpy as np

        if not crop_list:
            return []

        imgs = []
        for crop_arr, _ox, _oy, _spec, _ssim in crop_list:
            _, enc = cv2.imencode(".jpg", crop_arr)
            buf = np.frombuffer(enc.tobytes(), dtype=np.uint8)
            imgs.append(cv2.imdecode(buf, cv2.IMREAD_COLOR))

        results_list = []
        for i in range(0, len(imgs), sub_batch):
            chunk = imgs[i : i + sub_batch]
            results_list.extend(
                self._model.predict(chunk, imgsz=self._imgsz, conf=conf, iou=0.5, verbose=False)
            )

        all_dets: list[dict] = []
        for res, (_, ox, oy, spec_label, r_ssim) in zip(results_list, crop_list):
            boxes = getattr(res, "boxes", None)
            if boxes is None or boxes.xyxy is None or len(boxes) == 0:
                continue
            xyxy_list = boxes.xyxy.cpu().numpy().tolist()
            conf_list = boxes.conf.cpu().numpy().tolist()
            cls_list  = boxes.cls.cpu().numpy().astype(int).tolist()
            names = dict(res.names) if hasattr(res, "names") else {}
            for i in range(len(xyxy_list)):
                x1, y1, x2, y2 = [int(v) for v in xyxy_list[i]]
                all_dets.append({
                    "bbox_xyxy":   [ox + x1, oy + y1, ox + x2, oy + y2],
                    "confidence":  round(float(conf_list[i]), 4),
                    "class_name":  names.get(cls_list[i], str(cls_list[i])),
                    "from_crop":   spec_label,
                    "region_ssim": round(float(r_ssim), 4),
                })
        return all_dets


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

    def detect_image(self, name: str, image_bytes: bytes) -> Any:
        with self._lock:
            loaded = self._models.get(name)

        if loaded is None:
            raise KeyError(f"Model '{name}' is not loaded")

        if not isinstance(loaded.runtime_model, UltralyticsYoloRuntimeModel):
            raise ValueError(
                f"Model '{name}' backend '{loaded.backend}' does not support image detection"
            )

        result = loaded.runtime_model.predict(image_bytes)
        return _to_jsonable(result)

    def detect_crops_batch(
        self,
        name: str,
        crop_list: list,
        conf: float = 0.15,
        sub_batch: int = 4,
    ) -> list[dict]:
        """Batch-predict on a list of (crop_arr, ox, oy, spec_label, r_ssim) tuples.
        Returns dets with bbox projected to full-image coords."""
        with self._lock:
            loaded = self._models.get(name)

        if loaded is None:
            raise KeyError(f"Model '{name}' is not loaded")

        if not isinstance(loaded.runtime_model, UltralyticsYoloRuntimeModel):
            raise ValueError(
                f"Model '{name}' does not support batch crop detection"
            )

        return loaded.runtime_model.predict_crops_batch(crop_list, conf=conf, sub_batch=sub_batch)

    @staticmethod
    def _detect_backend(model_path: Path | None) -> str:
        if model_path is None:
            raise ValueError("Model path is required when backend is 'auto'")

        suffix = model_path.suffix.lower()
        if suffix == ".onnx":
            return "onnx"
        if suffix in {".pt", ".pth"}:
            # Project standard: .pt = Ultralytics YOLO weights.
            # For TorchScript files, set backend='torchscript' explicitly.
            return "yolo"

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

        if backend in {"yolo", "ultralytics"}:
            return UltralyticsYoloRuntimeModel(model_path)

        raise ValueError(f"Unsupported backend: {backend}")
