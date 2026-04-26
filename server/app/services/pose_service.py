from __future__ import annotations

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

    def health(self) -> dict[str, Any]:
        camera_exists = self._settings.artifact_camera_params.exists()
        g2o_status = "enabled" if pose_common.HAS_CPP else "fallback_only"
        lens_position = pose_common.load_camera_lens_position(
            str(self._settings.artifact_camera_params)
        )

        if camera_exists:
            message = f"Integrated Artifact-Pose module ready ({g2o_status})"
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
            "message": message,
        }

    def correct_image(self, image_path: Path) -> dict[str, Any]:
        K, D = pose_common.load_camera_params(self._settings.artifact_camera_params)
        if K is None:
            raise RuntimeError(f"Camera params not found: {self._settings.artifact_camera_params}")

        if not self._settings.artifact_golden_pose.exists():
            raise RuntimeError(f"Golden pose not found: {self._settings.artifact_golden_pose}")

        golden_pose = pose_common.load_golden_pose(self._settings.artifact_golden_pose)
        if golden_pose is None:
            raise RuntimeError(f"Golden pose not found: {self._settings.artifact_golden_pose}")

        image = cv2.imread(str(image_path))
        if image is None:
            raise RuntimeError(f"Can not read image: {image_path}")

        result = pose_correction.run_correction_step(image, K, D, golden_pose)
        result["integrated_module"] = True
        result["g2o_enabled"] = bool(pose_common.HAS_CPP)

        return _to_jsonable(result)

    def initialize_golden(
        self,
        left_image_path: Path,
        right_image_path: Path,
    ) -> dict[str, Any]:
        K, D = pose_common.load_camera_params(self._settings.artifact_camera_params)
        if K is None:
            raise RuntimeError(f"Camera params not found: {self._settings.artifact_camera_params}")

        left = cv2.imread(str(left_image_path))
        right = cv2.imread(str(right_image_path))
        if left is None or right is None:
            raise RuntimeError("Can not read left/right image for initialization")

        result = pose_initialize.run_initialization(
            left,
            right,
            K,
            D,
            output_pose_path=self._settings.artifact_golden_pose,
        )
        if result is None:
            raise RuntimeError("Golden initialization failed")

        return _to_jsonable(result)
