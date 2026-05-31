#!/usr/bin/env python3
"""
test_inspect_pipeline.py
Standalone test script — mirrors the full pipeline in inspection_service.py:
  SIFT Alignment → Multi-channel SSIM → Damage mask → Crop → YOLO per crop → Annotated output

Usage:
  cd /home/thepiece/System/Artifact-Pose-System/server
  python tools/test_inspect_pipeline.py \
    --reference data/uploads/artifacts/f86cb2/golden_left_f86cb2_1778823519555.png \
    --current   data/uploads/artifacts/f86cb2/final_aligned_f86cb2_1778824053659.png \
    --model     ../model/new-10-05-best.pt \
    --out       /tmp/inspect_test_out
"""

import argparse
import json
import sys
import time
from pathlib import Path

# ── helpers ─────────────────────────────────────────────────────────────────

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


def build_damage_mask(diff_uint8):
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
    """Suppress duplicate boxes across crop specs: keep highest-conf box per overlapping group (same class)."""
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


def yolo_detect_bytes(model, img_arr, conf=0.05):
    """Run YOLO on a numpy image array, return list of detection dicts."""
    import cv2
    import numpy as np
    _, enc = cv2.imencode(".jpg", img_arr)
    buf = np.frombuffer(enc.tobytes(), dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    results = model.predict(img, imgsz=960, conf=conf, iou=0.5, verbose=False)
    dets = []
    for res in results:
        boxes = getattr(res, "boxes", None)
        if boxes is None or boxes.xyxy is None or len(boxes) == 0:
            continue
        xyxy = boxes.xyxy.cpu().numpy().tolist()
        conf_list = boxes.conf.cpu().numpy().tolist()
        cls_list  = boxes.cls.cpu().numpy().astype(int).tolist()
        names = dict(res.names) if hasattr(res, "names") else {}
        for i in range(len(xyxy)):
            dets.append({
                "bbox_xyxy":  [int(v) for v in xyxy[i]],
                "confidence": round(float(conf_list[i]), 4),
                "class_name": names.get(cls_list[i], str(cls_list[i])),
            })
    return dets


# ── main pipeline ────────────────────────────────────────────────────────────

def run_pipeline(
    reference_path: Path,
    current_path: Path,
    model_path: Path,
    out_dir: Path,
    yolo_conf: float = 0.05,
    min_area_factor: float = 0.0001,
    damage_pct_threshold: float = 0.5,
    otsu_fallback: int = 60,
    sift_lowe: float = 0.65,
    sift_min_matches: int = 15,
    mode: str = "baseline",  # "baseline" | "hybrid"
):
    import cv2
    import numpy as np

    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_id = "test_f86cb2"
    ts_ms = int(time.time() * 1000)

    print("\n" + "="*60)
    print("STEP 0 — Load images")
    print("="*60)
    reference_img = cv2.imread(str(reference_path))
    current_img   = cv2.imread(str(current_path))
    assert reference_img is not None, f"Cannot read reference: {reference_path}"
    assert current_img   is not None, f"Cannot read current: {current_path}"
    print(f"  Reference shape : {reference_img.shape}")
    print(f"  Current   shape : {current_img.shape}")

    h, w = reference_img.shape[:2]
    cur_resized = cv2.resize(current_img, (w, h)) if current_img.shape[:2] != (h, w) else current_img.copy()

    # ── STEP 1: Alignment ───────────────────────────────────────────────────
    # YOLO always crops from the original pre-aligned image (yolo_source).
    # SSIM diff map / contour detection uses ssim_source:
    #   baseline → ssim_source = cur_resized  (no SIFT, direct comparison)
    #   hybrid   → ssim_source = SIFT-warped  (more precise diff map)
    print("\n" + "="*60)
    print(f"STEP 1 — Alignment  [mode: {mode.upper()}]")
    print("="*60)
    aligned_img  = None
    valid_mask   = None
    aligned_path = None
    yolo_source  = cur_resized  # YOLO always runs on the original pre-aligned image

    if mode == "hybrid":
        print("  [HYBRID] Running SIFT to compute precise diff map...")
        aligned_img, valid_mask, _inliers = sift_align_with_mask(cur_resized, reference_img)
        if aligned_img is not None:
            aligned_path = out_dir / f"aligned_{artifact_id}_{ts_ms}.jpg"
            cv2.imwrite(str(aligned_path), aligned_img)
            print(f"  SIFT-aligned image saved: {aligned_path}")
        ssim_source = aligned_img if aligned_img is not None else cur_resized
        print("  ssim_source = SIFT-aligned  |  yolo_source = original pre-aligned")
    else:
        # Baseline: SSIM directly on pre-aligned image, no auto-alignment
        print("  [BASELINE] No SIFT — using pre-aligned image directly.")
        ssim_source = cur_resized
        print("  ssim_source = yolo_source = original pre-aligned")

    # ── STEP 2: Multi-channel SSIM ──────────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 2 — Multi-channel SSIM")
    print("="*60)
    ssim_score, ssim_gray, ssim_color, diff_uint8 = compute_multi_ssim(ssim_source, reference_img, valid_mask)
    print(f"  SSIM (weighted)  : {ssim_score:.4f} ({ssim_score*100:.1f}%)")
    print(f"  SSIM gray        : {ssim_gray:.4f}")
    print(f"  SSIM color       : {ssim_color:.4f}")

    # ── STEP 3: Heatmap ─────────────────────────────────────────────────────
    heatmap = cv2.applyColorMap(diff_uint8, cv2.COLORMAP_JET)
    if valid_mask is not None:
        heatmap[cv2.bitwise_not(valid_mask) > 0] = [128, 128, 128]
    heatmap_overlay = cv2.addWeighted(ssim_source, 0.6, heatmap, 0.4, 0)
    heatmap_path = out_dir / f"heatmap_{artifact_id}_{ts_ms}.jpg"
    cv2.imwrite(str(heatmap_path), heatmap_overlay)
    print(f"  Heatmap saved   : {heatmap_path}")

    # ── STEP 4: Damage mask + contours ──────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 3 — Damage mask")
    print("="*60)
    damage_mask = build_damage_mask(diff_uint8)
    contours, _ = cv2.findContours(damage_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = max(500, (h * w) * min_area_factor)
    big_contours = [c for c in contours if cv2.contourArea(c) > min_area]
    print(f"  Total contours  : {len(contours)}")
    print(f"  min_area cutoff : {min_area:.0f} px² (factor={min_area_factor})")
    print(f"  Big contours    : {len(big_contours)}")

    valid_area = int(cv2.countNonZero(valid_mask)) if valid_mask is not None else (h * w)
    damage_area = sum(cv2.contourArea(c) for c in big_contours)
    damage_pct = (damage_area / max(valid_area, 1)) * 100.0
    print(f"  Damage area     : {damage_area:.0f} px²")
    print(f"  Valid area      : {valid_area} px²")
    print(f"  Damage %        : {damage_pct:.3f}%")

    cv2.drawContours(heatmap_overlay, big_contours, -1, (0, 0, 255), 2)
    cv2.imwrite(str(heatmap_path), heatmap_overlay)   # overwrite with contours drawn

    # ── STEP 5: Load YOLO model ──────────────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 4 — Load YOLO model")
    print("="*60)
    from ultralytics import YOLO
    yolo_model = YOLO(str(model_path))
    print(f"  Model loaded    : {model_path.name}")
    print(f"  Classes         : {dict(yolo_model.names)}")
    print(f"  conf threshold  : {yolo_conf}  (detections below this are invisible to pipeline)")

    # ── STEP 6: Crop → YOLO per crop ────────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 5 — Crop → YOLO per crop")
    print("="*60)

    _SEVERITY_COLOR = {
        "HIGH":   (0,   0,   255),
        "MEDIUM": (0,   128, 255),
        "LOW":    (0,   200, 128),
    }

    annotated = yolo_source.copy()  # annotations drawn on original pre-aligned image
    all_dets = []
    crop_regions = []

    GLOBAL_THRESHOLD_PCT = damage_pct_threshold
    if damage_pct < GLOBAL_THRESHOLD_PCT:
        print(f"  damage_pct {damage_pct:.3f}% < {GLOBAL_THRESHOLD_PCT}% threshold.")
        print("  → YOLO fallback: running on FULL image instead.")
        dets = yolo_detect_bytes(yolo_model, current_img, conf=yolo_conf)
        print(f"  Full-image detections: {len(dets)}")
        for _det in dets:
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
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1, cv2.LINE_AA)
            all_dets.append({**_det, "severity": _severity})
    else:
        # ── Crop specs per mode ──────────────────────────────────────────────
        # baseline : single crop, 30% padding  (original behaviour, no change)
        # hybrid   : tight (20% pad) + wide (70% pad), YOLO on both, then NMS merge
        #   tight → sharp/local defects: peel, scratch, writing_marks
        #   wide  → diffuse defects that need context: burn_mark, stain, material_loss
        if mode == "hybrid":
            # (label, pad_factor, min_pad_px)
            crop_specs = [("tight", 0.30, 40), ("wide", 0.70, 120)]
            _CROP_OUTLINE = {"tight": (0, 255, 255), "wide": (0, 128, 255)}
        else:
            crop_specs = [("single", 0.30, 40)]
            _CROP_OUTLINE = {"single": (255, 180, 0)}

        sorted_contours = sorted(big_contours, key=cv2.contourArea, reverse=True)
        print(f"  Processing {len(sorted_contours[:50])} contour(s) (cap=50), "
              f"{len(crop_specs)} crop spec(s) per ROI  [{mode.upper()}]...")

        for idx, contour in enumerate(sorted_contours[:50]):
            _bx, _by, _bw, _bh = cv2.boundingRect(contour)
            _side = max(_bw, _bh)
            _cxc  = _bx + _bw // 2
            _cyc  = _by + _bh // 2

            contour_dets  = []   # projected full-image detections from all specs (before NMS)
            primary_ssim  = 1.0
            primary_bbox  = [0, 0, 0, 0]
            primary_cpath = None

            for spec_label, pad_factor, min_pad in crop_specs:
                _pad  = max(min_pad, int(_side * pad_factor))
                _half = (_side // 2) + _pad
                _x1c  = max(0, _cxc - _half)
                _y1c  = max(0, _cyc - _half)
                _x2c  = min(w, _cxc + _half)
                _y2c  = min(h, _cyc + _half)
                if _x2c - _x1c < 40 or _y2c - _y1c < 40:
                    print(f"  Contour {idx} [{spec_label}]: too small, skipped.")
                    continue

                crop_arr   = yolo_source[_y1c:_y2c, _x1c:_x2c]
                crop_fname = out_dir / f"crop_{artifact_id}_{ts_ms}_{idx}_{spec_label}.jpg"
                cv2.imwrite(str(crop_fname), crop_arr)

                # Region SSIM
                from skimage.metrics import structural_similarity
                _ci  = cv2.cvtColor(crop_arr, cv2.COLOR_BGR2GRAY)
                _cr  = cv2.cvtColor(reference_img[_y1c:_y2c, _x1c:_x2c], cv2.COLOR_BGR2GRAY)
                _win = min(7, min(_ci.shape) - 1)
                if _win % 2 == 0: _win -= 1
                _r_ssim = float(structural_similarity(_cr, _ci, win_size=_win)) if _win >= 3 else 1.0

                # First spec is the primary (drives the crop summary entry)
                if primary_cpath is None:
                    primary_ssim  = _r_ssim
                    primary_bbox  = [_x1c, _y1c, _x2c, _y2c]
                    primary_cpath = crop_fname

                print(f"\n  Contour {idx} [{spec_label}]: "
                      f"bbox=[{_x1c},{_y1c},{_x2c},{_y2c}]  "
                      f"size={_x2c-_x1c}×{_y2c-_y1c}  region_ssim={_r_ssim:.4f}")

                # YOLO on this crop
                dets = yolo_detect_bytes(yolo_model, crop_arr, conf=yolo_conf)
                print(f"    YOLO detections [{spec_label}]: {len(dets)}")
                for d in dets:
                    print(f"      {d['class_name']:20s}  conf={d['confidence']:.3f}  "
                          f"bbox={d['bbox_xyxy']}")

                # Project to full-image coordinates and collect
                for _det in dets:
                    _cb = _det["bbox_xyxy"]
                    contour_dets.append({
                        "class_name":  _det["class_name"],
                        "confidence":  _det["confidence"],
                        "bbox_xyxy":   [_x1c + _cb[0], _y1c + _cb[1],
                                        _x1c + _cb[2], _y1c + _cb[3]],
                        "from_crop":   spec_label,
                        "region_ssim": round(_r_ssim, 4),
                    })

                # Draw crop region outline (colour encodes spec)
                cv2.rectangle(annotated, (_x1c, _y1c), (_x2c, _y2c),
                              _CROP_OUTLINE[spec_label], 1)

            # ── NMS across crop specs for this contour ───────────────────────
            if len(crop_specs) > 1 and contour_dets:
                _before = len(contour_dets)
                contour_dets = nms_detections(contour_dets, iou_threshold=0.45)
                print(f"  Contour {idx}: NMS {_before} → {len(contour_dets)} detection(s)")

            # ── Draw surviving detections ────────────────────────────────────
            crop_det_list = []
            for _det in contour_dets:
                x1, y1, x2, y2 = _det["bbox_xyxy"]
                _conf     = _det["confidence"]
                _name     = _det["class_name"]
                _severity = "HIGH" if _conf >= 0.65 else "MEDIUM" if _conf >= 0.40 else "LOW"
                _color    = _SEVERITY_COLOR[_severity]
                _tag      = f"[{_det['from_crop']}] " if mode == "hybrid" else ""
                _label    = f"{_tag}{_name} {_conf*100:.0f}% (SSIM {_det['region_ssim']*100:.0f}%)"
                _thickness = 3 if _severity == "HIGH" else 2
                cv2.rectangle(annotated, (x1, y1), (x2, y2), _color, _thickness)
                (_tw, _th), _bl = cv2.getTextSize(_label, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 1)
                _yt = max(0, y1 - _th - _bl - 4)
                cv2.rectangle(annotated, (x1, _yt), (x1+_tw+4, y1), _color, -1)
                cv2.putText(annotated, _label, (x1+2, y1-_bl-2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255,255,255), 1, cv2.LINE_AA)
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
                "area_pct":        round(float(cv2.contourArea(contour)) / max(valid_area, 1) * 100, 3),
                "detections":      crop_det_list,
                "crop_specs_used": [s[0] for s in crop_specs],
            })

    detect_path = out_dir / f"detect_{artifact_id}_{ts_ms}.jpg"
    cv2.imwrite(str(detect_path), annotated)

    # ── STEP 7: Classification ───────────────────────────────────────────────
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

    final_status = max(ssim_status, yolo_status, key=lambda s: {"GOOD":0,"WARNING":1,"DAMAGED":2}[s])
    print(f"  SSIM status     : {ssim_status}")
    print(f"  YOLO status     : {yolo_status} (max conf {max_conf:.3f})")
    print(f"  Final status    : {final_status}")

    # ── FINAL REPORT ────────────────────────────────────────────────────────
    report = {
        "pipeline_mode": mode,
        "ssim_summary": {
            "ssim": round(ssim_score, 4),
            "ssim_gray": round(ssim_gray, 4),
            "ssim_color": round(ssim_color, 4),
            "damage_pct": round(damage_pct, 3),
        },
        "damage_status": final_status,
        "all_detections": all_dets,
        "crops": crop_regions,
        "output_files": {
            "aligned": str(aligned_path) if aligned_img is not None else None,
            "heatmap": str(heatmap_path),
            "annotated": str(detect_path),
        },
    }
    report_path = out_dir / f"report_{artifact_id}_{ts_ms}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print("\n" + "="*60)
    print("DONE — Summary")
    print("="*60)
    print(f"  SSIM            : {ssim_score:.4f} ({ssim_score*100:.1f}%)")
    print(f"  Damage %        : {damage_pct:.3f}%")
    print(f"  Crop regions    : {len(crop_regions)}")
    print(f"  AI detections   : {len(all_dets)}")
    print(f"  Mode            : {mode.upper()}")
    print(f"  Status          : {final_status}")
    print(f"\n  Output dir      : {out_dir}")
    print(f"  Annotated image : {detect_path}")
    print(f"  Heatmap         : {heatmap_path}")
    print(f"  JSON report     : {report_path}")
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Test the full inspection pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Tuning guide:
  --conf          YOLO inference threshold. Lower = more detections (noisier).
                  0.05 shows everything; 0.40+ only high-confidence hits.
  --min-area      Fraction of image area for contour filter (default 0.0001).
                  Lower = catch smaller damage spots. 0.0001 → 829px² on 4K.
  --damage-pct    Global gate: skip AI entirely if damage% below this (default 0.5).
                  Lower catches subtle changes; raise to ignore lighting noise.
  --otsu-fallback Hard pixel threshold when Otsu result < 30 (default 60).
                  Lower = more sensitive diff map."""
    )
    parser.add_argument("--reference", required=False,
                        default="data/uploads/artifacts/f86cb2/golden_left_f86cb2_1778823519555.png")
    parser.add_argument("--current", required=False,
                        default="data/uploads/artifacts/f86cb2/final_aligned_f86cb2_1778824053659.png")
    parser.add_argument("--model", required=False,
                        default="../model/new-10-05-best.pt")
    parser.add_argument("--out", required=False,
                        default="/tmp/inspect_test_out")
    # ── Tunable parameters ──
    parser.add_argument("--conf",         type=float, default=0.05,
                        help="YOLO confidence threshold (default 0.05)")
    parser.add_argument("--min-area",     type=float, default=0.0001,
                        dest="min_area",
                        help="min_area factor relative to image size (default 0.0001)")
    parser.add_argument("--damage-pct",   type=float, default=0.5,
                        dest="damage_pct",
                        help="Global damage%% gate to trigger AI (default 0.5)")
    parser.add_argument("--otsu-fallback",type=int,   default=60,
                        dest="otsu_fallback",
                        help="Hard pixel threshold when Otsu<30 (default 60)")
    parser.add_argument("--mode",          type=str,   default="both",
                        choices=["baseline", "hybrid", "both"],
                        help="Pipeline mode: baseline (no SIFT), hybrid (SIFT for diff only), both (default)")
    args = parser.parse_args()

    ref_path  = Path(args.reference)
    cur_path  = Path(args.current)
    mdl_path  = Path(args.model)
    out_path  = Path(args.out)

    for p, name in [(ref_path, "reference"), (cur_path, "current"), (mdl_path, "model")]:
        if not p.exists():
            print(f"ERROR: {name} file not found: {p}", file=sys.stderr)
            sys.exit(1)

    _pipeline_kwargs = dict(
        yolo_conf=args.conf,
        min_area_factor=args.min_area,
        damage_pct_threshold=args.damage_pct,
        otsu_fallback=args.otsu_fallback,
    )
    if args.mode == "both":
        for _mode_name in ("baseline", "hybrid"):
            _out = out_path / _mode_name
            print(f"\n{'#'*60}")
            print(f"# Running mode: {_mode_name.upper()}")
            print(f"{'#'*60}")
            run_pipeline(ref_path, cur_path, mdl_path, _out,
                         mode=_mode_name, **_pipeline_kwargs)
    else:
        run_pipeline(ref_path, cur_path, mdl_path, out_path,
                     mode=args.mode, **_pipeline_kwargs)


if __name__ == "__main__":
    main()
