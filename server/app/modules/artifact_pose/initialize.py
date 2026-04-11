from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .common import (
    DATA_DIR,
    DIAMOND_OBJ_PTS,
    HAS_CPP,
    STEREO_BASELINE,
    detect_diamond,
    extract_orb,
    pose_solver_cpp,
    save_golden_pose,
)


def match_and_triangulate(
    desc_left: Any,
    kp_left: list[Any],
    desc_right: Any,
    kp_right: list[Any],
    K: Any,
    D: Any,
    baseline: float,
) -> tuple[Any, Any, Any, Any]:
    pts_left_arr = np.array([[kp.pt[0], kp.pt[1]] for kp in kp_left], dtype=np.float64)
    pts_right_arr = np.array([[kp.pt[0], kp.pt[1]] for kp in kp_right], dtype=np.float64)

    if HAS_CPP and pose_solver_cpp is not None:
        match_res = pose_solver_cpp.match_stereo(
            desc_left.astype(np.uint8),
            desc_right.astype(np.uint8),
        )
        matches = match_res["matches"]
        if len(matches) == 0:
            return None, None, None, None

        idx_l = np.array([m["query_idx"] for m in matches])
        idx_r = np.array([m["train_idx"] for m in matches])

        matched_left = pts_left_arr[idx_l]
        matched_right = pts_right_arr[idx_r]
        matched_desc = desc_left[idx_l]

        matched_left_u = cv2.undistortPoints(
            matched_left.reshape(-1, 1, 2).astype(np.float64), K, D, P=K
        ).reshape(-1, 2)
        matched_right_u = cv2.undistortPoints(
            matched_right.reshape(-1, 1, 2).astype(np.float64), K, D, P=K
        ).reshape(-1, 2)

        tri = pose_solver_cpp.triangulate_stereo(
            matched_left_u,
            matched_right_u,
            K.astype(np.float64),
            np.zeros(5, dtype=np.float64),
            baseline,
        )

        pts3d = np.array(tri["points_3d"])
        valid = list(tri["valid_mask"])
        mask = np.array(valid, dtype=bool)
        return pts3d[mask], matched_left[mask], matched_desc[mask], tri

    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    knn = bf.knnMatch(desc_left, desc_right, k=2)
    good = []
    for m_n in knn:
        if len(m_n) < 2:
            continue
        m, n = m_n
        if m.distance < 0.75 * n.distance:
            good.append(m)

    if len(good) < 20:
        return None, None, None, None

    pts_l = np.array([kp_left[m.queryIdx].pt for m in good])
    pts_r = np.array([kp_right[m.trainIdx].pt for m in good])
    m_desc = desc_left[np.array([m.queryIdx for m in good])]

    P1 = K @ np.hstack([np.eye(3), np.zeros((3, 1))])
    t = np.array([[baseline], [0], [0]])
    P2 = K @ np.hstack([np.eye(3), -t])
    pts4d = cv2.triangulatePoints(P1, P2, pts_l.T.astype(np.float64), pts_r.T.astype(np.float64))
    pts3d = (pts4d[:3] / pts4d[3]).T

    mask = (pts3d[:, 2] > 0.1) & (pts3d[:, 2] < 10.0)
    return pts3d[mask], pts_l[mask], m_desc[mask], None


def run_initialization(
    image_left: Any,
    image_right: Any,
    K: Any,
    D: Any,
    output_pose_path: str | Path | None = None,
) -> dict[str, Any] | None:
    diamond = detect_diamond(image_left, K, D)
    if diamond is None:
        return None

    kp_left, desc_left, _ = extract_orb(image_left)
    kp_right, desc_right, _ = extract_orb(image_right)

    pts3d, pts2d, matched_desc, _ = match_and_triangulate(
        desc_left,
        kp_left,
        desc_right,
        kp_right,
        K,
        D,
        STEREO_BASELINE,
    )

    if pts3d is None or len(pts3d) < 10:
        return None

    diamond_2d_undist = cv2.undistortPoints(
        diamond["corners"].reshape(-1, 1, 2).astype(np.float64), K, D, P=K
    ).reshape(-1, 2)
    _, rvec_pinhole, tvec_pinhole = cv2.solvePnP(
        DIAMOND_OBJ_PTS.astype(np.float64),
        diamond_2d_undist,
        K,
        None,
    )

    rvec_pinhole = rvec_pinhole.ravel()
    tvec_pinhole = tvec_pinhole.ravel()

    R_mat, _ = cv2.Rodrigues(rvec_pinhole)
    tvec_col = tvec_pinhole.reshape(3, 1)
    pts3d_world = (R_mat.T @ (pts3d.T - tvec_col)).T

    diamond["rvec"] = rvec_pinhole
    diamond["tvec"] = tvec_pinhole

    output_path = Path(output_pose_path) if output_pose_path is not None else DATA_DIR / "golden_pose.yaml"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    save_golden_pose(
        output_path,
        diamond,
        pts3d_world,
        pts2d,
        matched_desc,
        (image_left.shape[1], image_left.shape[0]),
        STEREO_BASELINE,
    )

    return {
        "diamond": diamond,
        "points_3d": pts3d_world,
        "points_2d": pts2d,
        "descriptors": matched_desc,
    }
