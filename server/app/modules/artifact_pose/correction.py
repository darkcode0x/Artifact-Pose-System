from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from .common import (
    HAS_CPP,
    ROT_TOLERANCE,
    TRANS_TOLERANCE,
    extract_orb,
    pose_solver_cpp,
)


def _match_with_reference_fallback(
    current_kp_xy: Any,
    current_desc: Any,
    ref_points_3d: Any,
    ref_descriptors: Any,
) -> tuple[Any, Any, int]:
    if (
        current_desc is None
        or ref_descriptors is None
        or len(current_desc) == 0
        or len(ref_descriptors) == 0
        or len(current_kp_xy) == 0
        or len(ref_points_3d) == 0
    ):
        return np.empty((0, 3), dtype=np.float64), np.empty((0, 2), dtype=np.float64), 0

    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    knn = bf.knnMatch(current_desc, ref_descriptors, k=2)

    good = []
    for m_n in knn:
        if len(m_n) < 2:
            continue
        m, n = m_n
        if m.distance < 0.75 * n.distance and m.distance <= 64:
            good.append(m)

    if not good:
        return np.empty((0, 3), dtype=np.float64), np.empty((0, 2), dtype=np.float64), 0

    current_idx = np.array([m.queryIdx for m in good], dtype=np.int32)
    ref_idx = np.array([m.trainIdx for m in good], dtype=np.int32)

    points_2d = np.array(current_kp_xy[current_idx], dtype=np.float64)
    points_3d = np.array(ref_points_3d[ref_idx], dtype=np.float64)
    return points_3d, points_2d, len(good)


def _match_with_reference(
    current_kp_xy: Any,
    current_desc: Any,
    ref_points_3d: Any,
    ref_descriptors: Any,
) -> tuple[Any, Any, int]:
    if (
        current_desc is None
        or ref_descriptors is None
        or len(current_desc) == 0
        or len(ref_descriptors) == 0
        or len(current_kp_xy) == 0
        or len(ref_points_3d) == 0
    ):
        return np.empty((0, 3), dtype=np.float64), np.empty((0, 2), dtype=np.float64), 0

    if HAS_CPP and pose_solver_cpp is not None:
        match_res = pose_solver_cpp.match_with_3d_reference(
            np.array(current_kp_xy, dtype=np.float64),
            np.array(current_desc, dtype=np.uint8),
            np.array(ref_points_3d, dtype=np.float64),
            np.array(ref_descriptors, dtype=np.uint8),
        )
        num_matches = int(match_res.get("num_matches", 0))
        if num_matches <= 0:
            return np.empty((0, 3), dtype=np.float64), np.empty((0, 2), dtype=np.float64), 0

        points_3d = np.array(match_res["points_3d"], dtype=np.float64)
        points_2d = np.array(match_res["points_2d"], dtype=np.float64)
        return points_3d, points_2d, num_matches

    return _match_with_reference_fallback(
        current_kp_xy,
        current_desc,
        ref_points_3d,
        ref_descriptors,
    )


def run_correction_step(image: Any, K: Any, D: Any, golden_pose: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "diamond": None,
        "anchor": None,
        "hybrid": None,
        "deviation": None,
        "motor_command": None,
        "num_orb_matches": 0,
        "num_orb_inliers": 0,
        "timing": {},
        "solver": "opencv_pnp",
        "g2o_enabled": bool(HAS_CPP),
    }

    t0 = time.time()
    _, desc_current, kp_xy = extract_orb(image)
    result["timing"]["features_ms"] = (time.time() - t0) * 1000

    ref_pts3d = golden_pose.get("points_3d")
    ref_desc = golden_pose.get("descriptors")
    if (
        ref_pts3d is None
        or ref_desc is None
        or len(ref_pts3d) == 0
        or len(ref_desc) == 0
        or len(kp_xy) == 0
        or len(desc_current) == 0
    ):
        result["reason"] = "insufficient_reference_or_features"
        return result

    t0 = time.time()
    orb_3d, orb_2d, num_matches = _match_with_reference(
        kp_xy,
        desc_current,
        ref_pts3d,
        ref_desc,
    )
    result["timing"]["match_ms"] = (time.time() - t0) * 1000
    result["num_orb_matches"] = int(num_matches)

    if len(orb_3d) < 8:
        result["reason"] = "insufficient_matches"
        return result

    orb_2d_undist = cv2.undistortPoints(
        orb_2d.reshape(-1, 1, 2).astype(np.float64),
        K,
        D,
        P=K,
    ).reshape(-1, 2)

    t0 = time.time()
    ok, rvec_init, tvec_init, inliers = cv2.solvePnPRansac(
        np.array(orb_3d, dtype=np.float64),
        np.array(orb_2d_undist, dtype=np.float64),
        K,
        None,
        flags=cv2.SOLVEPNP_EPNP,
        iterationsCount=300,
        reprojectionError=2.5,
        confidence=0.995,
    )
    if not ok:
        ok, rvec_init, tvec_init = cv2.solvePnP(
            np.array(orb_3d, dtype=np.float64),
            np.array(orb_2d_undist, dtype=np.float64),
            K,
            None,
            flags=cv2.SOLVEPNP_EPNP,
        )
        if ok:
            inliers = np.arange(len(orb_3d), dtype=np.int32).reshape(-1, 1)

    result["timing"]["pnp_ms"] = (time.time() - t0) * 1000

    if not ok:
        result["reason"] = "pnp_failed"
        return result

    if inliers is None or len(inliers) == 0:
        inlier_idx = np.arange(len(orb_3d), dtype=np.int32)
    else:
        inlier_idx = np.array(inliers, dtype=np.int32).reshape(-1)

    orb_3d_inliers = np.array(orb_3d[inlier_idx], dtype=np.float64)
    orb_2d_inliers = np.array(orb_2d_undist[inlier_idx], dtype=np.float64)
    result["num_orb_inliers"] = int(len(orb_3d_inliers))

    rvec_final = np.array(rvec_init, dtype=np.float64).ravel()
    tvec_final = np.array(tvec_init, dtype=np.float64).ravel()

    if HAS_CPP and pose_solver_cpp is not None and len(orb_3d_inliers) >= 6:
        anchor_count = min(12, max(4, len(orb_3d_inliers) // 8))
        anchor_indices = np.linspace(
            0,
            len(orb_3d_inliers) - 1,
            num=anchor_count,
            dtype=np.int32,
        )
        anchor_3d = np.array(orb_3d_inliers[anchor_indices], dtype=np.float64)
        anchor_2d = np.array(orb_2d_inliers[anchor_indices], dtype=np.float64)

        result["anchor"] = {
            "count": int(len(anchor_indices)),
            "source": "orb_quadtree_inliers",
        }

        t0 = time.time()
        try:
            dist_coeffs = np.array(D, dtype=np.float64).ravel() if D is not None else np.zeros(5)
            hybrid = pose_solver_cpp.hybrid_optimize(
                np.array(rvec_final, dtype=np.float64),
                np.array(tvec_final, dtype=np.float64),
                anchor_3d,
                anchor_2d,
                np.array(orb_3d_inliers, dtype=np.float64),
                np.array(orb_2d_inliers, dtype=np.float64),
                np.array(K, dtype=np.float64),
                dist_coeffs,
            )
            result["hybrid"] = hybrid
            result["solver"] = "g2o_quadtree_cpp"
            rvec_final = np.array(hybrid["rvec"], dtype=np.float64)
            tvec_final = np.array(hybrid["tvec"], dtype=np.float64)
        except Exception as exc:
            result["hybrid"] = {
                "error": str(exc),
            }
            result["solver"] = "opencv_pnp"
        result["timing"]["hybrid_ms"] = (time.time() - t0) * 1000

    t0 = time.time()
    if HAS_CPP and pose_solver_cpp is not None:
        deviation = pose_solver_cpp.calculate_deviation(
            golden_pose["rvec"].tolist(),
            golden_pose["tvec"].tolist(),
            rvec_final.tolist(),
            tvec_final.tolist(),
            TRANS_TOLERANCE,
            ROT_TOLERANCE,
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
        within_tolerance = trans_mag < TRANS_TOLERANCE and rot_mag < ROT_TOLERANCE

        # Keep fallback motor command behavior close to C++ path to avoid stalling
        # when native extension is unavailable.
        steps_per_mm = 860.0
        max_slider_steps = 10000.0
        max_rotate_deg = 25.0

        move_x = float(delta_t[0] * 1000.0 * steps_per_mm)
        move_z = float(delta_t[2] * 1000.0 * steps_per_mm)
        rotate_pan = float(pitch)
        rotate_tilt = float(roll)

        if not np.isfinite(move_x):
            move_x = 0.0
        if not np.isfinite(move_z):
            move_z = 0.0
        if not np.isfinite(rotate_pan):
            rotate_pan = 0.0
        if not np.isfinite(rotate_tilt):
            rotate_tilt = 0.0

        move_x = float(np.clip(move_x, -max_slider_steps, max_slider_steps))
        move_z = float(np.clip(move_z, -max_slider_steps, max_slider_steps))
        rotate_pan = float(np.clip(rotate_pan, -max_rotate_deg, max_rotate_deg))
        rotate_tilt = float(np.clip(rotate_tilt, -max_rotate_deg, max_rotate_deg))

        need_trans = trans_mag >= TRANS_TOLERANCE
        need_rot = rot_mag >= ROT_TOLERANCE
        if not need_trans and not need_rot:
            priority = 0
        elif need_trans and not need_rot:
            priority = 1
        elif not need_trans and need_rot:
            priority = 2
        else:
            priority = 3

        deviation = {
            "delta_x": float(delta_t[0]),
            "delta_y": float(delta_t[1]),
            "delta_z": float(delta_t[2]),
            "delta_pan": pitch,
            "delta_tilt": roll,
            "delta_roll": yaw,
            "translation_mag": trans_mag,
            "rotation_mag": rot_mag,
            "within_tolerance": within_tolerance,
            "motor_command": {
                "move_x": move_x,
                "move_z": move_z,
                "rotate_pan": rotate_pan,
                "rotate_tilt": rotate_tilt,
                "priority": priority,
            },
        }

    result["timing"]["deviation_ms"] = (time.time() - t0) * 1000
    result["deviation"] = deviation
    result["motor_command"] = deviation.get("motor_command")
    return result
