from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .common import (
    DATA_DIR,
    DEFAULT_REFERENCE_DEPTH,
    HAS_CPP,
    MIN_REFERENCE_POINTS,
    STEREO_BASELINE,
    build_reference_points_from_image_points,
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
    if (
        desc_left is None
        or desc_right is None
        or len(desc_left) == 0
        or len(desc_right) == 0
    ):
        return None, None, None, None

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


def _pick_strongest_indices(keypoints: list[Any], max_points: int) -> Any:
    if len(keypoints) <= max_points:
        return np.arange(len(keypoints), dtype=np.int32)

    scored = np.array([float(kp.response) for kp in keypoints], dtype=np.float64)
    indices = np.argsort(scored)[::-1][:max_points]
    return np.sort(indices.astype(np.int32))


def run_initialization(
    image_left: Any,
    image_right: Any,
    K: Any,
    D: Any,
    output_pose_path: str | Path | None = None,
    artifact_id: str | None = None,
) -> dict[str, Any] | None:
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

    if pts3d is None or len(pts3d) < MIN_REFERENCE_POINTS:
        return None

    # Use left-camera frame of the sampled stereo pair as reference frame.
    rvec_ref = np.zeros(3, dtype=np.float64)
    tvec_ref = np.zeros(3, dtype=np.float64)

    output_path = Path(output_pose_path) if output_pose_path is not None else DATA_DIR / "golden_pose.yaml"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    save_golden_pose(
        output_path,
        rvec_ref,
        tvec_ref,
        pts3d,
        pts2d,
        matched_desc,
        (image_left.shape[1], image_left.shape[0]),
        STEREO_BASELINE,
        method="quadtree_stereo_g2o",
        artifact_id=artifact_id,
        reference_depth=DEFAULT_REFERENCE_DEPTH,
    )

    return {
        "reference_pose": {
            "rvec": rvec_ref,
            "tvec": tvec_ref,
        },
        "points_3d": pts3d,
        "points_2d": pts2d,
        "descriptors": matched_desc,
        "num_points": int(len(pts3d)),
        "method": "quadtree_stereo_g2o",
        "artifact_id": artifact_id,
        "pose_file": str(output_path),
    }


def run_initialization_from_sample(
    image: Any,
    K: Any,
    D: Any,
    output_pose_path: str | Path | None = None,
    artifact_id: str | None = None,
    reference_depth: float = DEFAULT_REFERENCE_DEPTH,
    max_points: int = 2500,
) -> dict[str, Any] | None:
    keypoints, descriptors, keypoint_xy = extract_orb(image)
    if len(keypoints) < MIN_REFERENCE_POINTS or len(descriptors) < MIN_REFERENCE_POINTS:
        return None

    points_3d, points_2d = build_reference_points_from_image_points(
        keypoint_xy,
        K,
        D,
        reference_depth=reference_depth,
    )
    if len(points_3d) < MIN_REFERENCE_POINTS:
        return None

    keep_indices = _pick_strongest_indices(keypoints, max_points)
    points_3d = points_3d[keep_indices]
    points_2d = points_2d[keep_indices]
    descriptors = descriptors[keep_indices]

    rvec_ref = np.zeros(3, dtype=np.float64)
    tvec_ref = np.zeros(3, dtype=np.float64)

    output_path = Path(output_pose_path) if output_pose_path is not None else DATA_DIR / "golden_pose.yaml"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    save_golden_pose(
        output_path,
        rvec_ref,
        tvec_ref,
        points_3d,
        points_2d,
        descriptors,
        (image.shape[1], image.shape[0]),
        baseline=0.0,
        method="quadtree_mono_g2o",
        artifact_id=artifact_id,
        reference_depth=reference_depth,
    )

    return {
        "reference_pose": {
            "rvec": rvec_ref,
            "tvec": tvec_ref,
        },
        "points_3d": points_3d,
        "points_2d": points_2d,
        "descriptors": descriptors,
        "num_points": int(len(points_3d)),
        "method": "quadtree_mono_g2o",
        "artifact_id": artifact_id,
        "pose_file": str(output_path),
    }
