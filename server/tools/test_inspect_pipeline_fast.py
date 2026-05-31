#!/usr/bin/env python3
"""
test_inspect_pipeline_fast.py
Performance-optimised hybrid-only version of test_inspect_pipeline.py.

Key differences from the stable version:
  1. Batch YOLO inference  — all crops sent in one model.predict() call per batch
  2. Early-exit wide crop  — if tight crop already has high-conf detection, wide is skipped

Always runs in HYBRID mode:
  - SIFT used only to compute diff map (ssim_source)
  - YOLO always runs on original pre-aligned image (yolo_source)
  - Two crop specs per ROI: tight (30% pad) + wide (70% pad), NMS merge

Usage:
  docker exec -w /app artifact_server python tools/test_inspect_pipeline_fast.py \
    --model /app/model/new-10-05-best.pt \
    --conf 0.05 \
    --out /tmp/inspect_fast_out
"""

import argparse
import json
import sys
import time
from pathlib import Path


# ── helpers ──────────────────────────────────────────────────────────────────

def sift_align_with_mask(img, reference):
    """SIFT + Homography alignment. Returns (aligned, valid_mask, inlier_count)."""
    import cv2
    import numpy as np

    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_ref = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)

    sift = cv2.SIFT_create(nfeatures=3000)
    kp1, des1 = sift.detectAndCompute(gray_img, None)
    kp2, des2 = sift.detectAndCompute(gray_ref, None)

    print(f"  SIFT keypoints — source: {len(kp1)}, reference: {len(kp2)}")

    if des1 is None or des2 is None or len(kp1) < 15 or len(kp2) < 15:
        print("  [SIFT] Not enough keypoints, fallback to resize.")
        return cv2.resize(img, (reference.shape[1], reference.shape[0])), None, 0

    flann = cv2.FlannBasedMatcher({"algorithm": 1, "trees": 5}, {"checks": 50})
    matches = flann.knnMatch(des1, des2, k=2)
    good = [m for pair in matches if len(pair) == 2
            for m, n in [pair] if m.distance < 0.65 * n.distance]
    print(f"  SIFT good matches (Lowe 0.65): {len(good)}")

    if len(good) < 15:
        print("  [SIFT] Too few matches, fallback to resize.")
        return cv2.resize(img, (reference.shape[1], reference.shape[0])), None, len(good)

    src_pts = __import__("numpy").float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = __import__("numpy").float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    import numpy as np
    H, inlier_mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 3.0)
    if H is None:
        print("  [SIFT] Homography failed, fallback to resize.")
        return cv2.resize(img, (reference.shape[1], reference.shape[0])), None, len(good)

    inliers = int(inlier_mask.sum()) if inlier_mask is not None else 0
    print(f"  SIFT inliers: {inliers}")

    h, w = reference.shape[:2]
    aligned = cv2.warpPerspective(img, H, (w, h))

    ones = np.ones(img.shape[:2], dtype=np.uint8) * 255
    valid_mask = cv2.warpPerspective(ones, H, (w, h))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    valid_mask = cv2.erode(valid_mask, kernel, iterations=2)

    return aligned, valid_mask, inliers


def compute_multi_ssim(source, reference_img, valid_mask):
    """Multi-channel SSIM, returns (ssim_score, ssim_gray, ssim_color, diff_uint8)."""
    import cv2
    import numpy as np
    from skimage.metrics import structural_similarity

    gray_src = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
    gray_ref = cv2.cvtColor(reference_img, cv2.COLOR_BGR2GRAY)

    score_gray, diff_gray = structural_similarity(gray_ref, gray_src, full=True, win_size=7)

    score_channels = []
    diff_color = np.zeros_like(gray_src, dtype=np.float64)
    for c in range(3):
        sc, dc = structural_similarity(
            reference_img[:, :, c].astype(float),
            source[:, :, c].astype(float),
            full=True, win_size=7,
            data_range=255.0,
        )
        score_channels.append(sc)
        diff_color += (1.0 - dc)
    diff_color /= 3.0
    score_color = float(np.mean(score_channels))

    diff_combined = np.maximum(1.0 - diff_gray, diff_color)
    diff_uint8 = (diff_combined * 255).astype(np.uint8)

    if valid_mask is not None:
        diff_uint8 = cv2.bitwise_and(diff_uint8, valid_mask)

    ssim_score = 0.6 * float(score_gray) + 0.4 * score_color
    return ssim_score, float(score_gray), score_color, diff_uint8


def build_damage_mask(diff_uint8, otsu_fallback=60):
    import cv2
    blurred = cv2.GaussianBlur(diff_uint8, (5, 5), 0)
    otsu_thresh, damage_mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    print(f"  Otsu threshold: {otsu_thresh:.1f}")
    if otsu_thresh < 30:
        print(f"  Otsu < 30, using hard threshold {otsu_fallback}.")
        _, damage_mask = cv2.threshold(blurred, otsu_fallback, 255, cv2.THRESH_BINARY)

    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    kernel_big   = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    damage_mask = cv2.morphologyEx(damage_mask, cv2.MORPH_OPEN,  kernel_small, iterations=2)
    damage_mask = cv2.morphologyEx(damage_mask, cv2.MORPH_CLOSE, kernel_big,   iterations=2)
    return damage_mask


def nms_detections(dets, iou_threshold=0.5):
    """Suppress duplicate boxes: keep highest-conf box per overlapping group (same class)."""
    if not dets:
        return dets
    dets_sorted = sorted(dets, key=lambda d: d["confidence"], reverse=True)
    kept = []
    suppressed = set()
    for i, d in enumerate(dets_sorted):
        if i in suppressed:
            continue
        kept.append(d)
        bx1, by1, bx2, by2 = d["bbox_xyxy"]
        for j in range(i + 1, len(dets_sorted)):
            if j in suppressed:
                continue
            if dets_sorted[j]["class_name"] != d["class_name"]:
                continue
            cx1, cy1, cx2, cy2 = dets_sorted[j]["bbox_xyxy"]
            ix1, iy1 = max(bx1, cx1), max(by1, cy1)
            ix2, iy2 = min(bx2, cx2), min(by2, cy2)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            union = (bx2 - bx1) * (by2 - by1) + (cx2 - cx1) * (cy2 - cy1) - inter
            if union > 0 and inter / union > iou_threshold:
                suppressed.add(j)
    return kept


# ── OPTIMISATION: Batch YOLO ────────────────────────────────────────────────

def yolo_batch_predict(model, crop_list, conf=0.05, sub_batch=4):
    """
    Run YOLO on a list of (crop_arr, offset_x, offset_y, spec_label, r_ssim) tuples.
    Returns a flat list of detection dicts with coordinates projected to full-image space.
    Processes in sub-batches of `sub_batch` to avoid OOM on large contour sets.
    """
    import cv2
    import numpy as np

    if not crop_list:
        return []

    imgs = []
    for crop_arr, _ox, _oy, _spec, _ssim in crop_list:
        _, enc = cv2.imencode(".jpg", crop_arr)
        buf = np.frombuffer(enc.tobytes(), dtype=np.uint8)
        imgs.append(cv2.imdecode(buf, cv2.IMREAD_COLOR))

    # Run in sub-batches to stay within memory limits
    results_list = []
    for i in range(0, len(imgs), sub_batch):
        chunk = imgs[i:i + sub_batch]
        results_list.extend(model.predict(chunk, imgsz=960, conf=conf, iou=0.5, verbose=False))

    all_dets = []
    for res, (_, ox, oy, spec_label, r_ssim) in zip(results_list, crop_list):
        boxes = getattr(res, "boxes", None)
        if boxes is None or boxes.xyxy is None or len(boxes) == 0:
            continue
        xyxy      = boxes.xyxy.cpu().numpy().tolist()
        conf_list = boxes.conf.cpu().numpy().tolist()
        cls_list  = boxes.cls.cpu().numpy().astype(int).tolist()
        names     = dict(res.names) if hasattr(res, "names") else {}
        for i in range(len(xyxy)):
            x1, y1, x2, y2 = [int(v) for v in xyxy[i]]
            all_dets.append({
                "bbox_xyxy":   [ox + x1, oy + y1, ox + x2, oy + y2],
                "confidence":  round(float(conf_list[i]), 4),
                "class_name":  names.get(cls_list[i], str(cls_list[i])),
                "from_crop":   spec_label,
                "region_ssim": round(r_ssim, 4),
            })
    return all_dets


# ── main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    reference_path: Path,
    current_path: Path,
    model_path: Path,
    out_dir: Path,
    yolo_conf: float = 0.05,
    min_area_factor: float = 0.0001,
    damage_pct_threshold: float = 0.5,
    otsu_fallback: int = 60,
    early_exit_conf: float = 0.40,  # if tight crop has det >= this, skip wide
):
    import cv2
    import numpy as np
    from skimage.metrics import structural_similarity

    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_id = "test_f86cb2"
    ts_ms = int(time.time() * 1000)
    t0 = time.time()

    print("\n" + "="*60)
    print("STEP 0 — Load images  [HYBRID]")
    print("="*60)
    reference_img = cv2.imread(str(reference_path))
    current_img   = cv2.imread(str(current_path))
    assert reference_img is not None, f"Cannot read reference: {reference_path}"
    assert current_img   is not None, f"Cannot read current: {current_path}"
    print(f"  Reference shape : {reference_img.shape}")
    print(f"  Current   shape : {current_img.shape}")

    h, w = reference_img.shape[:2]
    cur_resized = cv2.resize(current_img, (w, h)) if current_img.shape[:2] != (h, w) else current_img.copy()

    # ── STEP 1: SIFT alignment (diff map only) ───────────────────────────────
    print("\n" + "="*60)
    print("STEP 1 — SIFT alignment (for diff map only)")
    print("="*60)
    aligned_img  = None
    valid_mask   = None
    aligned_path = None
    yolo_source  = cur_resized

    print("  Running SIFT to compute precise diff map...")
    t_sift = time.time()
    aligned_img, valid_mask, _inliers = sift_align_with_mask(cur_resized, reference_img)
    print(f"  SIFT done in {time.time()-t_sift:.2f}s")
    if aligned_img is not None:
        aligned_path = out_dir / f"aligned_{artifact_id}_{ts_ms}.jpg"
        cv2.imwrite(str(aligned_path), aligned_img)
    ssim_source = aligned_img if aligned_img is not None else cur_resized
    print("  ssim_source = SIFT-aligned  |  yolo_source = original pre-aligned")

    # ── STEP 2: Multi-channel SSIM ───────────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 2 — Multi-channel SSIM")
    print("="*60)
    t_ssim = time.time()
    ssim_score, ssim_gray, ssim_color, diff_uint8 = compute_multi_ssim(ssim_source, reference_img, valid_mask)
    print(f"  SSIM done in {time.time()-t_ssim:.2f}s")
    print(f"  SSIM (weighted)  : {ssim_score:.4f} ({ssim_score*100:.1f}%)")
    print(f"  SSIM gray        : {ssim_gray:.4f}")
    print(f"  SSIM color       : {ssim_color:.4f}")

    # ── STEP 3: Heatmap ──────────────────────────────────────────────────────
    heatmap = cv2.applyColorMap(diff_uint8, cv2.COLORMAP_JET)
    if valid_mask is not None:
        heatmap[cv2.bitwise_not(valid_mask) > 0] = [128, 128, 128]
    heatmap_overlay = cv2.addWeighted(ssim_source, 0.6, heatmap, 0.4, 0)
    heatmap_path = out_dir / f"heatmap_{artifact_id}_{ts_ms}.jpg"
    cv2.imwrite(str(heatmap_path), heatmap_overlay)

    # ── STEP 4: Damage mask + contours ───────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 3 — Damage mask + contours")
    print("="*60)
    damage_mask = build_damage_mask(diff_uint8, otsu_fallback)
    contours, _ = cv2.findContours(damage_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = max(500, (h * w) * min_area_factor)
    big_contours = [c for c in contours if cv2.contourArea(c) > min_area]
    big_contours = sorted(big_contours, key=cv2.contourArea, reverse=True)[:50]
    print(f"  Total contours  : {len(contours)}")
    print(f"  min_area cutoff : {min_area:.0f} px²  (factor={min_area_factor})")
    print(f"  ROI contours    : {len(big_contours)}  (capped at 50)")

    valid_area  = int(cv2.countNonZero(valid_mask)) if valid_mask is not None else (h * w)
    damage_area = sum(cv2.contourArea(c) for c in big_contours)
    damage_pct  = (damage_area / max(valid_area, 1)) * 100.0
    print(f"  Damage area     : {damage_area:.0f} px²")
    print(f"  Valid area      : {valid_area} px²")
    print(f"  Damage %        : {damage_pct:.3f}%")

    # Draw contour outlines on heatmap
    cv2.drawContours(heatmap_overlay, big_contours, -1, (0, 0, 255), 2)
    cv2.imwrite(str(heatmap_path), heatmap_overlay)

    # ── STEP 5: Load YOLO model ───────────────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 4 — Load YOLO model")
    print("="*60)
    from ultralytics import YOLO
    t_load = time.time()
    yolo_model = YOLO(str(model_path))
    print(f"  Model loaded in {time.time()-t_load:.2f}s : {model_path.name}")
    print(f"  Classes : {dict(yolo_model.names)}")
    print(f"  conf    : {yolo_conf}")

    # ── STEP 6: Build crop list → batch predict ───────────────────────────────
    print("\n" + "="*60)
    print("STEP 5 — Build crops → Batch YOLO  [HYBRID: tight + wide, early-exit]")
    print("="*60)

    _SEVERITY_COLOR = {
        "HIGH":   (0,   0,   255),
        "MEDIUM": (0,   128, 255),
        "LOW":    (0,   200, 128),
    }

    annotated    = yolo_source.copy()
    all_dets     = []
    crop_regions = []

    if damage_pct < damage_pct_threshold:
        print(f"  damage_pct {damage_pct:.3f}% < {damage_pct_threshold}% threshold.")
        print("  → YOLO fallback: running on FULL image instead.")
        t_yolo = time.time()
        full_dets = yolo_batch_predict(yolo_model, [(yolo_source, 0, 0, "full", 1.0)], conf=yolo_conf)
        print(f"  Full-image YOLO done in {time.time()-t_yolo:.2f}s  ({len(full_dets)} detections)")
        for _det in full_dets:
            x1, y1, x2, y2 = _det["bbox_xyxy"]
            _conf = _det["confidence"]
            _name = _det["class_name"]
            _severity = "HIGH" if _conf >= 0.65 else "MEDIUM" if _conf >= 0.40 else "LOW"
            _color = _SEVERITY_COLOR[_severity]
            cv2.rectangle(annotated, (x1, y1), (x2, y2), _color, 2)
            _label = f"{_name} {_conf*100:.0f}%"
            (_tw, _th), _bl = cv2.getTextSize(_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, max(0, y1-_th-_bl-4)), (x1+_tw+4, y1), _color, -1)
            cv2.putText(annotated, _label, (x1+2, y1-_bl-2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            all_dets.append({**_det, "severity": _severity})
    else:
        crop_specs = [("tight", 0.30, 40), ("wide", 0.70, 120)]
        _CROP_OUTLINE = {"tight": (0, 255, 255), "wide": (0, 128, 255)}

        # ── OPTIMISATION: Early-exit wide — two-phase batch ─────────────────────
        # Phase A: all tight crops → one batch predict
        # Phase B: only ROIs where tight gave no high-conf hit get wide crops

        # ── Compute crop bboxes for all ROI contours ───────────────────────────────
        roi_meta = []  # per ROI: list of spec dicts
        for idx, contour in enumerate(big_contours):
            rx, ry, rw, rh = cv2.boundingRect(contour)
            _side = max(rw, rh)
            _cxc  = rx + rw // 2
            _cyc  = ry + rh // 2
            specs_for_roi = []
            for spec_label, pad_factor, min_pad in crop_specs:
                _pad  = max(min_pad, int(_side * pad_factor))
                _half = (_side // 2) + _pad
                x1c   = max(0, _cxc - _half)
                y1c   = max(0, _cyc - _half)
                x2c   = min(w, _cxc + _half)
                y2c   = min(h, _cyc + _half)
                if x2c - x1c < 40 or y2c - y1c < 40:
                    continue
                crop_arr = yolo_source[y1c:y2c, x1c:x2c]
                # region SSIM
                _ci  = cv2.cvtColor(crop_arr, cv2.COLOR_BGR2GRAY)
                _cr  = cv2.cvtColor(reference_img[y1c:y2c, x1c:x2c], cv2.COLOR_BGR2GRAY)
                _win = min(7, min(_ci.shape) - 1)
                if _win % 2 == 0: _win -= 1
                r_ssim = float(structural_similarity(_cr, _ci, win_size=_win)) if _win >= 3 else 1.0
                specs_for_roi.append({
                    "spec": spec_label, "bbox": [x1c, y1c, x2c, y2c],
                    "crop": crop_arr,   "ssim": r_ssim,
                })
            roi_meta.append(specs_for_roi)

        print(f"  Processing {len(big_contours)} ROI(s), 2 specs each (tight + wide)")

        # Phase A — all tight crops in one batch
        tight_batch = []
        for specs in roi_meta:
            for s in specs:
                if s["spec"] == "tight":
                    tight_batch.append((s["crop"], s["bbox"][0], s["bbox"][1], "tight", s["ssim"]))

        t_yolo = time.time()
        print(f"  [Phase A] Running batch YOLO on {len(tight_batch)} tight crops (imgsz=960)...")
        tight_results = yolo_batch_predict(yolo_model, tight_batch, conf=yolo_conf)
        print(f"  Phase A done in {time.time()-t_yolo:.2f}s  → {len(tight_results)} raw detections")

        # Map tight detections back to ROI index
        tight_dets_per_roi = [[] for _ in roi_meta]
        for det in tight_results:
            for idx, specs in enumerate(roi_meta):
                for s in specs:
                    if s["spec"] != "tight":
                        continue
                    bx1, by1, bx2, by2 = s["bbox"]
                    dx1, dy1, dx2, dy2 = det["bbox_xyxy"]
                    if dx1 >= bx1 and dy1 >= by1 and dx2 <= bx2 and dy2 <= by2:
                        tight_dets_per_roi[idx].append(det)
                        break

        # Phase B — wide only for ROIs that tight didn’t cover confidently
        wide_batch = []
        skipped_wide = 0
        for idx, specs in enumerate(roi_meta):
            max_tight_conf = max((d["confidence"] for d in tight_dets_per_roi[idx]), default=0.0)
            if max_tight_conf >= early_exit_conf:
                skipped_wide += 1
                continue
            for s in specs:
                if s["spec"] == "wide":
                    wide_batch.append((s["crop"], s["bbox"][0], s["bbox"][1], "wide", s["ssim"]))

        if skipped_wide:
            print(f"  Early-exit: skipped wide for {skipped_wide} ROI(s) "
                  f"(tight conf >= {early_exit_conf})")

        t_yolo2 = time.time()
        if wide_batch:
            print(f"  [Phase B] Running batch YOLO on {len(wide_batch)} wide crops (imgsz=960)...")
        wide_results = yolo_batch_predict(yolo_model, wide_batch, conf=yolo_conf) if wide_batch else []
        if wide_batch:
            print(f"  Phase B done in {time.time()-t_yolo2:.2f}s  → {len(wide_results)} raw detections")

        all_raw_dets = tight_results + wide_results

        # Save crop images and draw outlines
        for idx, specs in enumerate(roi_meta):
            primary_bbox  = specs[0]["bbox"] if specs else [0, 0, 0, 0]
            primary_ssim  = specs[0]["ssim"] if specs else 1.0
            primary_cpath = None
            for s in specs:
                crop_fname = out_dir / f"crop_{artifact_id}_{ts_ms}_{idx}_{s['spec']}.jpg"
                cv2.imwrite(str(crop_fname), s["crop"])
                if primary_cpath is None:
                    primary_cpath = crop_fname
                bx1, by1, bx2, by2 = s["bbox"]
                cv2.rectangle(annotated, (bx1, by1), (bx2, by2),
                              _CROP_OUTLINE[s["spec"]], 1)

            # Collect dets belonging to this ROI's crop bboxes
            roi_raw = []
            for det in all_raw_dets:
                for s in specs:
                    bx1, by1, bx2, by2 = s["bbox"]
                    dx1, dy1, dx2, dy2 = det["bbox_xyxy"]
                    # allow small tolerance for projection
                    if (dx1 >= bx1 - 5 and dy1 >= by1 - 5 and
                            dx2 <= bx2 + 5 and dy2 <= by2 + 5 and
                            det["from_crop"] == s["spec"]):
                        roi_raw.append(det)
                        break

            # NMS across tight/wide specs
            if roi_raw:
                _before = len(roi_raw)
                roi_raw = nms_detections(roi_raw, iou_threshold=0.45)
                if len(roi_raw) < _before:
                    print(f"  ROI {idx}: NMS {_before} → {len(roi_raw)}")

            # Draw detections
            crop_det_list = []
            for _det in roi_raw:
                x1, y1, x2, y2 = _det["bbox_xyxy"]
                _conf     = _det["confidence"]
                _name     = _det["class_name"]
                _severity = "HIGH" if _conf >= 0.65 else "MEDIUM" if _conf >= 0.40 else "LOW"
                _color    = _SEVERITY_COLOR[_severity]
                _tag      = f"[{_det['from_crop']}] "
                _label    = f"{_tag}{_name} {_conf*100:.0f}% (SSIM {_det['region_ssim']*100:.0f}%)"
                _thickness = 3 if _severity == "HIGH" else 2
                cv2.rectangle(annotated, (x1, y1), (x2, y2), _color, _thickness)
                (_tw, _th), _bl = cv2.getTextSize(_label, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 1)
                _yt = max(0, y1 - _th - _bl - 4)
                cv2.rectangle(annotated, (x1, _yt), (x1+_tw+4, y1), _color, -1)
                cv2.putText(annotated, _label, (x1+2, y1-_bl-2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 1, cv2.LINE_AA)
                crop_det_list.append({
                    "class_name": _name,
                    "confidence": _conf,
                    "from_crop":  _det["from_crop"],
                })
                all_dets.append({
                    "class_name":       _name,
                    "confidence":       _conf,
                    "bbox_xyxy":        [x1, y1, x2, y2],
                    "crop_path":        str(primary_cpath) if primary_cpath else "",
                    "crop_region_ssim": _det["region_ssim"],
                    "from_crop":        _det["from_crop"],
                    "severity":         _severity,
                })

            crop_regions.append({
                "index":           idx,
                "crop_path":       str(primary_cpath) if primary_cpath else "",
                "region_bbox":     primary_bbox,
                "region_ssim":     round(primary_ssim, 4),
                "area_pct":        round((primary_bbox[2]-primary_bbox[0]) *
                                         (primary_bbox[3]-primary_bbox[1]) /
                                         max(valid_area, 1) * 100, 3),
                "detections":      crop_det_list,
                "crop_specs_used": [s["spec"] for s in specs],
            })

    detect_path = out_dir / f"detect_{artifact_id}_{ts_ms}.jpg"
    cv2.imwrite(str(detect_path), annotated)

    # ── STEP 7: Classification ────────────────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 6 — Damage classification")
    print("="*60)
    max_conf = max((d["confidence"] for d in all_dets), default=0.0)
    if ssim_score >= 0.95 and damage_pct < 2:
        ssim_status = "GOOD"
    elif ssim_score >= 0.85 and damage_pct < 10:
        ssim_status = "WARNING"
    else:
        ssim_status = "DAMAGED"

    if max_conf >= 0.65:
        yolo_status = "DAMAGED"
    elif max_conf >= 0.40:
        yolo_status = "WARNING"
    else:
        yolo_status = "GOOD"

    final_status = max(ssim_status, yolo_status,
                       key=lambda s: {"GOOD": 0, "WARNING": 1, "DAMAGED": 2}[s])
    print(f"  SSIM status     : {ssim_status}")
    print(f"  YOLO status     : {yolo_status} (max conf {max_conf:.3f})")
    print(f"  Final status    : {final_status}")

    total_time = time.time() - t0

    # ── FINAL REPORT ─────────────────────────────────────────────────────────
    report = {
        "pipeline_mode": "hybrid",
        "total_time_s":  round(total_time, 2),
        "ssim_summary": {
            "ssim":       round(ssim_score, 4),
            "ssim_gray":  round(ssim_gray, 4),
            "ssim_color": round(ssim_color, 4),
            "damage_pct": round(damage_pct, 3),
        },
        "contour_stats": {
            "raw_contours": len(big_contours),
        },
        "damage_status":    final_status,
        "all_detections":   all_dets,
        "crops":            crop_regions,
        "output_files": {
            "aligned":   str(aligned_path) if aligned_img is not None else None,
            "heatmap":   str(heatmap_path),
            "annotated": str(detect_path),
        },
    }
    report_path = out_dir / f"report_{artifact_id}_{ts_ms}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print("\n" + "="*60)
    print("DONE — Summary")
    print("="*60)
    print(f"  Mode            : HYBRID")
    print(f"  SSIM            : {ssim_score:.4f} ({ssim_score*100:.1f}%)")
    print(f"  Damage %        : {damage_pct:.3f}%")
    print(f"  ROI contours    : {len(big_contours)}")
    print(f"  Crop regions    : {len(crop_regions)}")
    print(f"  AI detections   : {len(all_dets)}")
    print(f"  Status          : {final_status}")
    print(f"  Total time      : {total_time:.2f}s")
    print(f"\n  Output dir      : {out_dir}")
    print(f"  Annotated image : {detect_path}")
    print(f"  Heatmap         : {heatmap_path}")
    print(f"  JSON report     : {report_path}")
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Fast inspection pipeline — hybrid only (batch YOLO + early-exit wide).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Performance knobs:
  --early-exit-conf If tight crop already has det >= this conf, skip wide (default 0.40).
                    Set to 1.0 to disable early-exit (always run both specs).

Detection knobs (same as stable version):
  --conf            YOLO confidence threshold (default 0.05)
  --min-area        Contour size filter factor (default 0.0001)
  --damage-pct      Global SSIM gate to trigger YOLO (default 0.5)
  --otsu-fallback   Hard threshold when Otsu < 30 (default 60)"""
    )
    parser.add_argument("--reference", required=False,
                        default="data/uploads/artifacts/f86cb2/golden_left_f86cb2_1778823519555.png")
    parser.add_argument("--current", required=False,
                        default="data/uploads/artifacts/f86cb2/final_aligned_f86cb2_1778824053659.png")
    parser.add_argument("--model",   required=False, default="../model/new-10-05-best.pt")
    parser.add_argument("--out",     required=False, default="/tmp/inspect_fast_out")
    parser.add_argument("--conf",          type=float, default=0.05)
    parser.add_argument("--min-area",      type=float, default=0.0001, dest="min_area")
    parser.add_argument("--damage-pct",    type=float, default=0.5,    dest="damage_pct")
    parser.add_argument("--otsu-fallback", type=int,   default=60,     dest="otsu_fallback")
    parser.add_argument("--early-exit-conf", type=float, default=0.40, dest="early_exit_conf",
                        help="Skip wide crop if tight conf >= this value (default 0.40)")
    args = parser.parse_args()

    ref_path = Path(args.reference)
    cur_path = Path(args.current)
    mdl_path = Path(args.model)
    out_path = Path(args.out)

    for p, name in [(ref_path, "reference"), (cur_path, "current"), (mdl_path, "model")]:
        if not p.exists():
            print(f"ERROR: {name} file not found: {p}", file=sys.stderr)
            sys.exit(1)

    run_pipeline(
        ref_path, cur_path, mdl_path, out_path,
        yolo_conf=args.conf,
        min_area_factor=args.min_area,
        damage_pct_threshold=args.damage_pct,
        otsu_fallback=args.otsu_fallback,
        early_exit_conf=args.early_exit_conf,
    )


if __name__ == "__main__":
    main()
