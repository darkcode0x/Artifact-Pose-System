from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from cv2 import aruco

SERVER_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = SERVER_ROOT / "data"
PARAMS_FILE = DATA_DIR / "camera_params_4k.yaml"
GOLDEN_POSE_FILE = DATA_DIR / "golden_pose.yaml"
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

SQUARE_LENGTH = 0.040
MARKER_LENGTH = 0.025
DICT_ID = aruco.DICT_4X4_50
STEREO_BASELINE = 0.10

HALF_SQ = SQUARE_LENGTH / 2.0
DIAMOND_OBJ_PTS = np.array(
    [
        [-HALF_SQ, HALF_SQ, 0],
        [HALF_SQ, HALF_SQ, 0],
        [HALF_SQ, -HALF_SQ, 0],
        [-HALF_SQ, -HALF_SQ, 0],
    ],
    dtype=np.float32,
)

TRANS_TOLERANCE = float(os.environ.get("TRANS_TOLERANCE_MM", "10.0")) / 1000.0  # env in mm, stored in m
ROT_TOLERANCE = float(os.environ.get("ROT_TOLERANCE_DEG", "1.0"))               # degrees

# Motor hardware constants
SERVO_MIN_DEG = 1.0      # Minimum servo rotation step (degrees)
SEQUENTIAL_MODE = True   # Translation first, rotation on next iteration
STEPS_PER_MM = float(os.environ.get("STEPS_PER_MM", "860.0"))  # Stepper motor steps per mm


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


def detect_diamond(image: Any, K: Any, D: Any) -> dict[str, Any] | None:
    dictionary = aruco.getPredefinedDictionary(DICT_ID)
    diamond_board = aruco.CharucoBoard((3, 3), SQUARE_LENGTH, MARKER_LENGTH, dictionary)

    params = aruco.DetectorParameters()
    params.cornerRefinementMethod = aruco.CORNER_REFINE_SUBPIX
    params.cornerRefinementWinSize = 5
    params.cornerRefinementMaxIterations = 30
    params.cornerRefinementMinAccuracy = 0.01

    detector = aruco.CharucoDetector(diamond_board)
    detector.setDetectorParameters(params)

    diamond_corners, diamond_ids, _, _ = detector.detectDiamonds(image)
    if diamond_ids is None or len(diamond_ids) == 0:
        return None

    img_pts = diamond_corners[0].reshape(-1, 2).astype(np.float64)
    ok, rvec, tvec = cv2.solvePnP(
        DIAMOND_OBJ_PTS,
        img_pts,
        K,
        D,
        flags=cv2.SOLVEPNP_IPPE_SQUARE,
    )

    if not ok:
        return None

    return {
        "rvec": rvec.ravel(),
        "tvec": tvec.ravel(),
        "corners": img_pts,
        "obj_pts": DIAMOND_OBJ_PTS,
    }


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

        descriptors = np.array(result["descriptors"], dtype=np.uint8)
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

    if keypoints:
        kp_xy = np.array([[kp.pt[0], kp.pt[1]] for kp in keypoints], dtype=np.float64)
    else:
        kp_xy = np.empty((0, 2), dtype=np.float64)

    return keypoints, descriptors, kp_xy


def load_golden_pose(filepath: str | Path | None = None) -> dict[str, Any] | None:
    path = _as_path(filepath, GOLDEN_POSE_FILE)
    fs = cv2.FileStorage(str(path), cv2.FileStorage_READ)
    if not fs.isOpened():
        return None

    rvec_node = fs.getNode("rvec_diamond")
    tvec_node = fs.getNode("tvec_diamond")
    if rvec_node.empty() or tvec_node.empty():
        fs.release()
        return None

    rvec = rvec_node.mat().ravel()
    tvec = tvec_node.mat().ravel()
    points_3d = fs.getNode("points_3d").mat()
    points_2d = fs.getNode("points_2d").mat()

    baseline_node = fs.getNode("baseline")
    baseline = baseline_node.real() if not baseline_node.empty() else STEREO_BASELINE
    fs.release()

    desc_path = path.with_name(path.stem + "_descriptors.npy")
    descriptors = np.load(str(desc_path)) if desc_path.exists() else None

    return {
        "rvec": rvec,
        "tvec": tvec,
        "points_3d": points_3d,
        "points_2d": points_2d,
        "descriptors": descriptors,
        "baseline": baseline,
    }


def save_golden_pose(
    filepath: str | Path,
    diamond_result: dict[str, Any],
    points_3d: Any,
    points_2d: Any,
    descriptors: Any,
    image_size: tuple[int, int],
    baseline: float,
) -> None:
    from datetime import datetime

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    fs = cv2.FileStorage(str(path), cv2.FileStorage_WRITE)

    rvec_arr = np.array(diamond_result["rvec"], dtype=np.float64).reshape(3, 1)
    tvec_arr = np.array(diamond_result["tvec"], dtype=np.float64).reshape(3, 1)
    corners_arr = np.array(diamond_result["corners"], dtype=np.float32)

    fs.write("rvec_diamond", rvec_arr)
    fs.write("tvec_diamond", tvec_arr)
    fs.write("corners_diamond", corners_arr)

    pts3d_arr = np.array(points_3d, dtype=np.float64)
    pts2d_arr = np.array(points_2d, dtype=np.float32)

    fs.write("num_points", int(len(points_3d)))
    fs.write("points_3d", pts3d_arr)
    fs.write("points_2d", pts2d_arr)

    fs.write("baseline", float(baseline))
    fs.write("image_width", int(image_size[0]))
    fs.write("image_height", int(image_size[1]))
    fs.write("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    fs.release()

    desc_path = path.with_name(path.stem + "_descriptors.npy")
    np.save(str(desc_path), descriptors)
