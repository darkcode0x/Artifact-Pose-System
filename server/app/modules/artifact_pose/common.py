from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np

SERVER_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = SERVER_ROOT / "data"
PARAMS_FILE = DATA_DIR / "camera_params_4k.yaml"
GOLDEN_POSE_FILE = DATA_DIR / "golden_pose.yaml"
GOLDEN_ARTIFACTS_DIR = DATA_DIR / "golden_artifacts"
VIS_DIR = DATA_DIR / "visualization"

def _prepare_native_runtime() -> None:
    if os.name == "nt":
        for dll_dir in (
            SERVER_ROOT / "native" / "install-ucrt64" / "bin",
            Path("D:/msys2/ucrt64/bin"),
        ):
            if dll_dir.exists():
                try:
                    os.add_dll_directory(str(dll_dir))
                except OSError:
                    pass
        return

    if os.name == "posix":
        import ctypes

        mode = getattr(ctypes, "RTLD_GLOBAL", 0)
        for so_dir in (
            SERVER_ROOT / "native" / "install-linux" / "lib",
            SERVER_ROOT / "native" / "install" / "lib",
            Path("/usr/local/lib"),
            Path("/usr/lib/x86_64-linux-gnu"),
            Path("/usr/lib"),
        ):
            if not so_dir.exists():
                continue

            for pattern in ("libg2o*.so*", "libcholmod.so*", "libcxsparse.so*"):
                for so_path in sorted(so_dir.glob(pattern)):
                    try:
                        ctypes.CDLL(str(so_path), mode=mode)
                    except OSError:
                        pass


_prepare_native_runtime()

try:
    from . import pose_solver_cpp  # type: ignore

    HAS_CPP = True
except Exception:
    try:
        import pose_solver_cpp  # type: ignore

        HAS_CPP = True
    except Exception:
        pose_solver_cpp = None
        HAS_CPP = False

STEREO_BASELINE = 0.10
DEFAULT_REFERENCE_DEPTH = 1.0
MIN_REFERENCE_POINTS = 40

TRANS_TOLERANCE = 0.005
ROT_TOLERANCE = 0.5


def _as_path(value: str | Path | None, default: Path) -> Path:
    if value is None:
        return default
    path = Path(value)
    return path


def load_camera_params(filepath: str | Path | None = None) -> tuple[Any, Any]:
    path = _as_path(filepath, PARAMS_FILE)
    fs = cv2.FileStorage(str(path), cv2.FileStorage_READ)
    if not fs.isOpened():
        return None, None

    K = fs.getNode("camera_matrix").mat()
    D = fs.getNode("distortion_coefficients").mat()
    fs.release()
    return K, D


def load_camera_lens_position(filepath: str | Path | None = None) -> float | None:
    path = _as_path(filepath, PARAMS_FILE)
    fs = cv2.FileStorage(str(path), cv2.FileStorage_READ)
    if not fs.isOpened():
        return None

    node = fs.getNode("lens_position")
    lens_position = None if node.empty() else float(node.real())
    fs.release()
    return lens_position


def extract_orb(
    image: Any,
    max_features: int = 5000,
    min_node_size: int = 64,
    max_depth: int = 7,
) -> tuple[list[Any], Any, Any]:
    if HAS_CPP and pose_solver_cpp is not None:
        result = pose_solver_cpp.extract_with_quadtree(
            image,
            max_features,
            min_node_size,
            max_depth,
        )

        keypoints = [
            cv2.KeyPoint(
                x=kp["x"],
                y=kp["y"],
                size=kp["size"],
                angle=kp["angle"],
                response=kp["response"],
            )
            for kp in result["keypoints"]
        ]

        descriptors_raw = result.get("descriptors")
        if descriptors_raw is None:
            descriptors = np.empty((0, 32), dtype=np.uint8)
        else:
            descriptors = np.array(descriptors_raw, dtype=np.uint8)
            if descriptors.ndim != 2:
                descriptors = np.empty((0, 32), dtype=np.uint8)

        if len(result["keypoints"]) > 0:
            kp_xy = np.array(
                [[kp["x"], kp["y"]] for kp in result["keypoints"]],
                dtype=np.float64,
            )
        else:
            kp_xy = np.empty((0, 2), dtype=np.float64)

        return keypoints, descriptors, kp_xy

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    orb = cv2.ORB_create(max_features)
    keypoints, descriptors = orb.detectAndCompute(gray, None)
    keypoints = list(keypoints) if keypoints else []
    if descriptors is None:
        descriptors = np.empty((0, 32), dtype=np.uint8)

    if keypoints:
        kp_xy = np.array([[kp.pt[0], kp.pt[1]] for kp in keypoints], dtype=np.float64)
    else:
        kp_xy = np.empty((0, 2), dtype=np.float64)

    return keypoints, descriptors, kp_xy


def build_reference_points_from_image_points(
    image_points: Any,
    K: Any,
    D: Any,
    reference_depth: float = DEFAULT_REFERENCE_DEPTH,
) -> tuple[Any, Any]:
    if image_points is None or len(image_points) == 0:
        return np.empty((0, 3), dtype=np.float64), np.empty((0, 2), dtype=np.float64)

    image_points_arr = np.array(image_points, dtype=np.float64).reshape(-1, 1, 2)
    undist_norm = cv2.undistortPoints(image_points_arr, K, D).reshape(-1, 2)
    undist_pixel = cv2.undistortPoints(image_points_arr, K, D, P=K).reshape(-1, 2)

    z_value = float(reference_depth)
    points_3d = np.column_stack(
        [
            undist_norm[:, 0] * z_value,
            undist_norm[:, 1] * z_value,
            np.full(undist_norm.shape[0], z_value, dtype=np.float64),
        ]
    )
    return points_3d.astype(np.float64), undist_pixel.astype(np.float64)


def load_golden_pose(filepath: str | Path | None = None) -> dict[str, Any] | None:
    path = _as_path(filepath, GOLDEN_POSE_FILE)
    fs = cv2.FileStorage(str(path), cv2.FileStorage_READ)
    if not fs.isOpened():
        return None

    rvec_node = fs.getNode("rvec_ref")
    tvec_node = fs.getNode("tvec_ref")
    if rvec_node.empty() or tvec_node.empty():
        rvec_node = fs.getNode("rvec_diamond")
        tvec_node = fs.getNode("tvec_diamond")

    if rvec_node.empty() or tvec_node.empty():
        fs.release()
        return None

    rvec = rvec_node.mat().ravel()
    tvec = tvec_node.mat().ravel()

    points_3d_node = fs.getNode("points_3d")
    points_2d_node = fs.getNode("points_2d")
    points_3d = points_3d_node.mat() if not points_3d_node.empty() else None
    points_2d = points_2d_node.mat() if not points_2d_node.empty() else None

    baseline_node = fs.getNode("baseline")
    baseline = baseline_node.real() if not baseline_node.empty() else STEREO_BASELINE

    method_node = fs.getNode("method")
    method = method_node.string() if not method_node.empty() else "legacy"

    artifact_id_node = fs.getNode("artifact_id")
    artifact_id = artifact_id_node.string() if not artifact_id_node.empty() else None

    ref_depth_node = fs.getNode("reference_depth")
    reference_depth = (
        float(ref_depth_node.real())
        if not ref_depth_node.empty()
        else float(DEFAULT_REFERENCE_DEPTH)
    )

    fs.release()

    desc_path = path.with_name(path.stem + "_descriptors.npy")
    descriptors = np.load(str(desc_path)) if desc_path.exists() else np.empty((0, 32), dtype=np.uint8)

    if points_3d is None:
        points_3d = np.empty((0, 3), dtype=np.float64)
    if points_2d is None:
        points_2d = np.empty((0, 2), dtype=np.float64)

    return {
        "rvec": rvec,
        "tvec": tvec,
        "points_3d": points_3d,
        "points_2d": points_2d,
        "descriptors": descriptors,
        "baseline": baseline,
        "method": method,
        "artifact_id": artifact_id,
        "reference_depth": reference_depth,
    }


def save_golden_pose(
    filepath: str | Path,
    rvec: Any,
    tvec: Any,
    points_3d: Any,
    points_2d: Any,
    descriptors: Any,
    image_size: tuple[int, int],
    baseline: float,
    method: str,
    artifact_id: str | None = None,
    reference_depth: float = DEFAULT_REFERENCE_DEPTH,
) -> None:
    from datetime import datetime

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    fs = cv2.FileStorage(str(path), cv2.FileStorage_WRITE)

    rvec_arr = np.array(rvec, dtype=np.float64).reshape(3, 1)
    tvec_arr = np.array(tvec, dtype=np.float64).reshape(3, 1)

    # Keep both new and legacy keys to avoid breaking older readers.
    fs.write("rvec_ref", rvec_arr)
    fs.write("tvec_ref", tvec_arr)
    fs.write("rvec_diamond", rvec_arr)
    fs.write("tvec_diamond", tvec_arr)

    pts3d_arr = np.array(points_3d, dtype=np.float64)
    pts2d_arr = np.array(points_2d, dtype=np.float32)

    fs.write("num_points", int(len(pts3d_arr)))
    fs.write("points_3d", pts3d_arr)
    fs.write("points_2d", pts2d_arr)

    fs.write("baseline", float(baseline))
    fs.write("reference_depth", float(reference_depth))
    fs.write("image_width", int(image_size[0]))
    fs.write("image_height", int(image_size[1]))
    fs.write("method", str(method))
    if artifact_id:
        fs.write("artifact_id", str(artifact_id))
    fs.write("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    fs.release()

    descriptors_arr = np.array(descriptors, dtype=np.uint8)
    if descriptors_arr.ndim != 2:
        descriptors_arr = np.empty((0, 32), dtype=np.uint8)

    desc_path = path.with_name(path.stem + "_descriptors.npy")
    np.save(str(desc_path), descriptors_arr)
