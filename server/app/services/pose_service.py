from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.modules.artifact_pose import common as pose_common
from app.modules.artifact_pose import correction as pose_correction
from app.modules.artifact_pose import initialize as pose_initialize
from app.core.config import Settings


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


class PoseService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._module_root = Path(__file__).resolve().parents[1] / "modules" / "artifact_pose"
        self._artifact_golden_dir = self._settings.data_dir / "golden_artifacts"
        self._artifact_golden_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sanitize_artifact_id(artifact_id: str | None) -> str:
        value = (artifact_id or "artifact_demo_001").strip()
        if not value:
            value = "artifact_demo_001"
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", value)
        safe = safe.strip("_")
        return safe or "artifact_demo_001"

    def _artifact_pose_path(self, artifact_id: str | None) -> Path:
        safe_id = self._sanitize_artifact_id(artifact_id)
        return self._artifact_golden_dir / f"{safe_id}.yaml"

    def _resolve_existing_pose_path(self, artifact_id: str | None) -> Path:
        artifact_path = self._artifact_pose_path(artifact_id)
        if artifact_path.exists():
            return artifact_path

        safe_id = self._sanitize_artifact_id(artifact_id)
        if safe_id == "artifact_demo_001" and self._settings.artifact_golden_pose.exists():
            return self._settings.artifact_golden_pose

        return artifact_path

    def _build_artifact_status(self, artifact_id: str | None) -> dict[str, Any]:
        safe_id = self._sanitize_artifact_id(artifact_id)
        pose_path = self._resolve_existing_pose_path(safe_id)

        details: dict[str, Any] = {
            "artifact_id": artifact_id or safe_id,
            "safe_artifact_id": safe_id,
            "pose_file": str(pose_path),
            "exists": pose_path.exists(),
            "method": None,
            "num_points": 0,
            "updated_at": None,
        }

        if not pose_path.exists():
            return details

        golden = pose_common.load_golden_pose(str(pose_path))
        if golden is not None:
            points_3d = golden.get("points_3d")
            details["method"] = golden.get("method")
            details["num_points"] = int(len(points_3d)) if points_3d is not None else 0

            stored_artifact = golden.get("artifact_id")
            if isinstance(stored_artifact, str) and stored_artifact.strip():
                details["artifact_id"] = stored_artifact.strip()

        try:
            details["updated_at"] = datetime.fromtimestamp(pose_path.stat().st_mtime).isoformat()
        except OSError:
            details["updated_at"] = None

        return details

    def list_artifacts(self) -> list[dict[str, Any]]:
        artifacts_by_id: dict[str, dict[str, Any]] = {}

        for pose_file in sorted(self._artifact_golden_dir.glob("*.yaml")):
            artifact_id = pose_file.stem
            status = self._build_artifact_status(artifact_id)
            artifacts_by_id[status["safe_artifact_id"]] = status

        legacy_default = self._build_artifact_status("artifact_demo_001")
        artifacts_by_id[legacy_default["safe_artifact_id"]] = legacy_default

        return sorted(artifacts_by_id.values(), key=lambda item: item["safe_artifact_id"])

    def artifact_status(self, artifact_id: str) -> dict[str, Any]:
        return self._build_artifact_status(artifact_id)

    def health(self) -> dict[str, Any]:
        camera_exists = self._settings.artifact_camera_params.exists()
        g2o_status = "enabled" if pose_common.HAS_CPP else "fallback_only"
        lens_position = pose_common.load_camera_lens_position(
            str(self._settings.artifact_camera_params)
        )

        if camera_exists:
            message = (
                "Integrated Artifact-Pose module ready "
                f"({g2o_status}, quadtree_feature_reference)"
            )
        else:
            message = (
                f"Integrated module loaded but camera params missing: "
                f"{self._settings.artifact_camera_params}"
            )

        return {
            "ok": True,
            "available": camera_exists,
            "artifact_pose_root": str(self._module_root),
            "camera_params_dir": str(self._settings.artifact_camera_params_dir),
            "camera_params": str(self._settings.artifact_camera_params),
            "configured_lens_position": self._settings.artifact_lens_position,
            "camera_lens_position": lens_position,
            "golden_pose": str(self._settings.artifact_golden_pose),
            "artifact_golden_dir": str(self._artifact_golden_dir),
            "message": message,
        }

    def correct_image(self, image_path: Path, artifact_id: str | None = None) -> dict[str, Any]:
        K, D = pose_common.load_camera_params(str(self._settings.artifact_camera_params))
        if K is None:
            raise RuntimeError(f"Camera params not found: {self._settings.artifact_camera_params}")

        pose_path = self._resolve_existing_pose_path(artifact_id)
        if not pose_path.exists():
            raise RuntimeError(
                f"Golden pose not found for artifact '{self._sanitize_artifact_id(artifact_id)}': {pose_path}"
            )

        golden_pose = pose_common.load_golden_pose(str(pose_path))
        if golden_pose is None:
            raise RuntimeError(f"Golden pose not found: {pose_path}")

        image = cv2.imread(str(image_path))
        if image is None:
            raise RuntimeError(f"Can not read image: {image_path}")

        result = pose_correction.run_correction_step(image, K, D, golden_pose)
        result["integrated_module"] = True
        result["g2o_enabled"] = bool(pose_common.HAS_CPP)
        result["artifact_id"] = artifact_id or self._sanitize_artifact_id(artifact_id)
        result["golden_pose_file"] = str(pose_path)
        result["reference_method"] = golden_pose.get("method")

        return _to_jsonable(result)

    def initialize_golden(
        self,
        left_image_path: Path,
        right_image_path: Path,
        artifact_id: str | None = None,
    ) -> dict[str, Any]:
        K, D = pose_common.load_camera_params(str(self._settings.artifact_camera_params))
        if K is None:
            raise RuntimeError(f"Camera params not found: {self._settings.artifact_camera_params}")

        left = cv2.imread(str(left_image_path))
        right = cv2.imread(str(right_image_path))
        if left is None or right is None:
            raise RuntimeError("Can not read left/right image for initialization")

        safe_artifact = self._sanitize_artifact_id(artifact_id)
        output_pose_path = self._artifact_pose_path(safe_artifact)

        result = pose_initialize.run_initialization(
            left,
            right,
            K,
            D,
            output_pose_path=output_pose_path,
            artifact_id=safe_artifact,
        )
        if result is None:
            raise RuntimeError("Golden initialization failed")

        result["artifact_status"] = self.artifact_status(safe_artifact)
        return _to_jsonable(result)

    def initialize_from_sample(
        self,
        image_path: Path,
        artifact_id: str,
    ) -> dict[str, Any]:
        K, D = pose_common.load_camera_params(str(self._settings.artifact_camera_params))
        if K is None:
            raise RuntimeError(f"Camera params not found: {self._settings.artifact_camera_params}")

        image = cv2.imread(str(image_path))
        if image is None:
            raise RuntimeError(f"Can not read sample image: {image_path}")

        safe_artifact = self._sanitize_artifact_id(artifact_id)
        output_pose_path = self._artifact_pose_path(safe_artifact)

        result = pose_initialize.run_initialization_from_sample(
            image,
            K,
            D,
            output_pose_path=output_pose_path,
            artifact_id=safe_artifact,
        )
        if result is None:
            raise RuntimeError("Sample initialization failed (insufficient ORB reference points)")

        result["artifact_status"] = self.artifact_status(safe_artifact)
        return _to_jsonable(result)
