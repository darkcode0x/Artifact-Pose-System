from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .common import (
    DIAMOND_OBJ_PTS,
    HAS_CPP,
    ROT_TOLERANCE,
    SEQUENTIAL_MODE,
    SERVO_MIN_DEG,
    STEPS_PER_MM,
    TRANS_TOLERANCE,
    detect_diamond,
    extract_orb,
    pose_solver_cpp,
)


def run_correction_step(image: Any, K: Any, D: Any, golden_pose: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "diamond": None,
        "hybrid": None,
        "deviation": None,
        "motor_command": None,
        "num_orb_matches": 0,
        "timing": {},
        "solver": "opencv_fallback",
        "g2o_enabled": bool(HAS_CPP),
    }

    t0 = time.time()
    diamond = detect_diamond(image, K, D)
    result["timing"]["diamond_ms"] = (time.time() - t0) * 1000

    if diamond is None:
        return result

    result["diamond"] = diamond
    diamond_3d = DIAMOND_OBJ_PTS.astype(np.float64)
    diamond_2d = diamond["corners"].astype(np.float64)

    t0 = time.time()
    _, desc_current, kp_xy = extract_orb(image)
    result["timing"]["orb_ms"] = (time.time() - t0) * 1000

    orb_3d = np.empty((0, 3), dtype=np.float64)
    orb_2d = np.empty((0, 2), dtype=np.float64)

    ref_pts3d = golden_pose.get("points_3d")
    ref_desc = golden_pose.get("descriptors")

    if (
        HAS_CPP
        and pose_solver_cpp is not None
        and ref_pts3d is not None
        and ref_desc is not None
        and len(ref_pts3d) > 0
        and len(ref_desc) > 0
        and desc_current is not None
        and len(desc_current) > 0
    ):
        t0 = time.time()
        match_res = pose_solver_cpp.match_with_3d_reference(
            kp_xy.astype(np.float64),
            desc_current.astype(np.uint8),
            np.array(ref_pts3d, dtype=np.float64),
            np.array(ref_desc, dtype=np.uint8),
        )
        result["timing"]["match_ms"] = (time.time() - t0) * 1000
        result["num_orb_matches"] = match_res["num_matches"]

        if match_res["num_matches"] > 0:
            orb_3d = np.array(match_res["points_3d"], dtype=np.float64)
            orb_2d = np.array(match_res["points_2d"], dtype=np.float64)

    if HAS_CPP and pose_solver_cpp is not None:
        diamond_2d_undist = cv2.undistortPoints(
            diamond_2d.reshape(-1, 1, 2), K, D, P=K
        ).reshape(-1, 2)

        if len(orb_2d) > 0:
            orb_2d_undist = cv2.undistortPoints(
                orb_2d.reshape(-1, 1, 2), K, D, P=K
            ).reshape(-1, 2)
        else:
            orb_2d_undist = orb_2d

        _, rvec_init, tvec_init = cv2.solvePnP(diamond_3d, diamond_2d_undist, K, None)

        t0 = time.time()
        hybrid = pose_solver_cpp.hybrid_optimize(
            rvec_init.ravel().astype(np.float64),
            tvec_init.ravel().astype(np.float64),
            diamond_3d,
            diamond_2d_undist,
            orb_3d,
            orb_2d_undist,
            K.astype(np.float64),
            D.ravel().astype(np.float64),
        )
        result["timing"]["hybrid_ms"] = (time.time() - t0) * 1000
        result["hybrid"] = hybrid
        result["solver"] = "g2o_hybrid_cpp"

        rvec_final = np.array(hybrid["rvec"])
        tvec_final = np.array(hybrid["tvec"])
    else:
        rvec_final = diamond["rvec"]
        tvec_final = diamond["tvec"]

    t0 = time.time()
    if HAS_CPP and pose_solver_cpp is not None:
        deviation = pose_solver_cpp.calculate_deviation(
            golden_pose["rvec"].tolist(),
            golden_pose["tvec"].tolist(),
            rvec_final.tolist(),
            tvec_final.tolist(),
            TRANS_TOLERANCE,
            ROT_TOLERANCE,
            SERVO_MIN_DEG,
            SEQUENTIAL_MODE,
            STEPS_PER_MM,
        )
    else:
        delta_t = tvec_final - golden_pose["tvec"]
        trans_mag = float(np.linalg.norm(delta_t))

        R_golden, _ = cv2.Rodrigues(golden_pose["rvec"])
        R_current, _ = cv2.Rodrigues(rvec_final)
        R_diff = R_current @ R_golden.T

        sy = np.sqrt(R_diff[0, 0] ** 2 + R_diff[1, 0] ** 2)
        if sy > 1e-6:
            roll = np.degrees(np.arctan2(R_diff[2, 1], R_diff[2, 2]))
            pitch = np.degrees(np.arctan2(-R_diff[2, 0], sy))
            yaw = np.degrees(np.arctan2(R_diff[1, 0], R_diff[0, 0]))
        else:
            roll = np.degrees(np.arctan2(-R_diff[1, 2], R_diff[1, 1]))
            pitch = np.degrees(np.arctan2(-R_diff[2, 0], sy))
            yaw = 0.0

        rot_mag = float(np.sqrt(roll**2 + pitch**2 + yaw**2))
        within_trans = trans_mag < TRANS_TOLERANCE
        within_rot = rot_mag < ROT_TOLERANCE
        deviation = {
            "delta_x": float(delta_t[0]),
            "delta_y": float(delta_t[1]),
            "delta_z": float(delta_t[2]),
            "delta_pan": pitch,
            "delta_tilt": roll,
            "delta_roll": yaw,
            "translation_mag": trans_mag,
            "rotation_mag": rot_mag,
            "within_tolerance": within_trans and within_rot,
            "within_trans_tolerance": within_trans,
            "within_rot_tolerance": within_rot,
            "motor_command": {
                "move_x": 0,
                "move_z": 0,
                "rotate_pan": 0,
                "rotate_tilt": 0,
                "priority": 0,
            },
        }

    result["timing"]["deviation_ms"] = (time.time() - t0) * 1000
    result["deviation"] = deviation
    result["motor_command"] = deviation.get("motor_command")
    return result
