"""
Pipeline phan tich hu hai co vat: YOLO Detection + SSIM Analysis

Pipeline:
  1. YOLO detect: Tim vung hu hai (bounding box + class) tren anh kiem tra
  2. SSIM global: So sanh toan bo anh kiem tra voi anh goc (reference)
  3. SSIM per-region: Tinh SSIM rieng cho tung vung YOLO detect duoc
  4. Severity scoring: Ket hop YOLO confidence + SSIM -> muc do nghiem trong
  5. Report: Xuat bao cao + visualization

Cach dung:
  # Pipeline day du (YOLO + SSIM)
  python analyze_damage.py --image test.jpg --reference ref.jpg --model best.pt

  # Chi SSIM (khong can YOLO)
  python analyze_damage.py --image test.jpg --reference ref.jpg

  # Batch: so sanh nhieu anh voi 1 reference
  python analyze_damage.py --image_dir images/ --reference ref.jpg --model best.pt

  # Tu dong chon reference (cach cu)
  python analyze_damage.py --face face1 --processed_dir processed/
"""
import cv2
import numpy as np
from skimage.metrics import structural_similarity
import os
import argparse
import json


CLASS_NAMES = {
    0: "material_loss", 1: "peel", 2: "scratch", 3: "fold",
    4: "writing_marks", 5: "dirt", 6: "staning", 7: "burn_marks",
}

SEVERITY_COLORS = {
    "NONE": (0, 255, 0),      # Xanh la
    "LOW": (0, 200, 255),     # Vang
    "MEDIUM": (0, 128, 255),  # Cam
    "HIGH": (0, 0, 255),      # Do
}


# =====================================================================
# SSIM FUNCTIONS (cai tien)
# =====================================================================

def align_with_sift(img, reference):
    """Align img voi reference bang SIFT + Homography."""
    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_ref = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)

    sift = cv2.SIFT_create(nfeatures=3000)
    kp1, des1 = sift.detectAndCompute(gray_img, None)
    kp2, des2 = sift.detectAndCompute(gray_ref, None)

    if des1 is None or des2 is None or len(kp1) < 15 or len(kp2) < 15:
        return cv2.resize(img, (reference.shape[1], reference.shape[0])), None, 0

    index_params = dict(algorithm=1, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)
    matches = flann.knnMatch(des1, des2, k=2)

    good = []
    for pair in matches:
        if len(pair) == 2:
            m, n = pair
            if m.distance < 0.65 * n.distance:
                good.append(m)

    if len(good) < 15:
        return cv2.resize(img, (reference.shape[1], reference.shape[0])), None, len(good)

    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    H, inlier_mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 3.0)
    if H is None:
        return cv2.resize(img, (reference.shape[1], reference.shape[0])), None, len(good)

    inliers = int(inlier_mask.sum()) if inlier_mask is not None else 0
    h, w = reference.shape[:2]
    aligned = cv2.warpPerspective(img, H, (w, h))

    ones = np.ones(img.shape[:2], dtype=np.uint8) * 255
    valid_mask = cv2.warpPerspective(ones, H, (w, h))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    valid_mask = cv2.erode(valid_mask, kernel, iterations=2)

    return aligned, valid_mask, inliers


def compute_ssim(img, reference, valid_mask=None):
    """
    Tinh SSIM giua img va reference.

    Cai tien so voi ban cu:
    - Multi-channel SSIM (so sanh ca mau, khong chi grayscale)
    - Adaptive threshold (Otsu thay vi fixed 80)
    - Gaussian blur truoc khi threshold (giam noise)

    Returns: dict voi ssim_score, damage_mask, heatmap, overlay, ...
    """
    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_ref = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)

    # === SSIM grayscale (structure) ===
    score_gray, diff_gray = structural_similarity(
        gray_ref, gray_img, full=True, win_size=7,
    )

    # === SSIM per-channel (color) — phat hien staning, burn tot hon ===
    score_channels = []
    diff_color = np.zeros_like(gray_img, dtype=np.float64)
    for c in range(3):
        sc, dc = structural_similarity(
            reference[:, :, c], img[:, :, c], full=True, win_size=7,
        )
        score_channels.append(sc)
        diff_color += (1.0 - dc)
    diff_color = diff_color / 3.0  # Average difference across channels
    score_color = np.mean(score_channels)

    # === Ket hop: lay max difference (grayscale hoac color) ===
    diff_combined = np.maximum(1.0 - diff_gray, diff_color)
    diff_uint8 = (diff_combined * 255).astype(np.uint8)

    # SSIM tong hop = trung binh co trong (gray 60% + color 40%)
    ssim_score = 0.6 * score_gray + 0.4 * score_color

    # Ap dung valid mask
    if valid_mask is not None:
        diff_uint8 = cv2.bitwise_and(diff_uint8, valid_mask)

    # === Adaptive threshold (Otsu - tu dong tim nguong) ===
    blurred = cv2.GaussianBlur(diff_uint8, (5, 5), 0)
    otsu_thresh, damage_mask = cv2.threshold(
        blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    # Fallback: neu Otsu threshold qua thap (< 30), dung fixed threshold
    if otsu_thresh < 30:
        _, damage_mask = cv2.threshold(blurred, 60, 255, cv2.THRESH_BINARY)

    # Morphological filtering
    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    kernel_big = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    damage_mask = cv2.morphologyEx(damage_mask, cv2.MORPH_OPEN, kernel_small, iterations=2)
    damage_mask = cv2.morphologyEx(damage_mask, cv2.MORPH_CLOSE, kernel_big, iterations=2)

    # Heatmap
    heatmap = cv2.applyColorMap(diff_uint8, cv2.COLORMAP_JET)
    if valid_mask is not None:
        inv_mask = cv2.bitwise_not(valid_mask)
        heatmap[inv_mask > 0] = [128, 128, 128]

    # Overlay
    overlay = cv2.addWeighted(img, 0.6, heatmap, 0.4, 0)

    # Contours
    contours, _ = cv2.findContours(damage_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = max(500, (reference.shape[0] * reference.shape[1]) * 0.0005)
    big_contours = [c for c in contours if cv2.contourArea(c) > min_area]
    cv2.drawContours(overlay, big_contours, -1, (0, 0, 255), 2)

    # Damage %
    if valid_mask is not None:
        valid_area = cv2.countNonZero(valid_mask)
    else:
        valid_area = reference.shape[0] * reference.shape[1]

    damage_area = sum(cv2.contourArea(c) for c in big_contours)
    damage_pct = (damage_area / max(valid_area, 1)) * 100

    return {
        "ssim_score": ssim_score,
        "ssim_gray": score_gray,
        "ssim_color": score_color,
        "damage_pct": damage_pct,
        "damage_mask": damage_mask,
        "heatmap": heatmap,
        "overlay": overlay,
        "num_regions": len(big_contours),
        "contours": big_contours,
    }


def compute_region_ssim(img, reference, x1, y1, x2, y2, padding=20):
    """Tinh SSIM cho 1 vung (bbox tu YOLO) — co padding xung quanh."""
    h, w = img.shape[:2]
    # Expand bbox with padding
    px1 = max(0, x1 - padding)
    py1 = max(0, y1 - padding)
    px2 = min(w, x2 + padding)
    py2 = min(h, y2 + padding)

    crop_img = img[py1:py2, px1:px2]
    crop_ref = reference[py1:py2, px1:px2]

    if crop_img.shape[0] < 16 or crop_img.shape[1] < 16:
        return 1.0  # Qua nho, khong tinh duoc

    gray_img = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
    gray_ref = cv2.cvtColor(crop_ref, cv2.COLOR_BGR2GRAY)

    win = min(7, min(gray_img.shape) - 1)
    if win % 2 == 0:
        win -= 1
    if win < 3:
        return 1.0

    score, _ = structural_similarity(gray_ref, gray_img, full=True, win_size=win)
    return score


# =====================================================================
# YOLO FUNCTIONS
# =====================================================================

def load_yolo_model(model_path):
    """Load YOLO model."""
    from ultralytics import YOLO
    model = YOLO(model_path)
    print(f"YOLO model loaded: {model_path}")
    return model


def yolo_detect(model, image_path, conf=0.25, iou=0.5):
    """Chay YOLO detection tren 1 anh. Returns list of detections."""
    results = model.predict(image_path, conf=conf, iou=iou, verbose=False)
    detections = []
    for r in results:
        boxes = r.boxes
        for i in range(len(boxes)):
            x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy().astype(int)
            conf_score = float(boxes.conf[i].cpu())
            cls_id = int(boxes.cls[i].cpu())
            detections.append({
                "bbox": (x1, y1, x2, y2),
                "class_id": cls_id,
                "class_name": CLASS_NAMES.get(cls_id, f"class_{cls_id}"),
                "confidence": conf_score,
            })
    return detections


# =====================================================================
# SEVERITY SCORING
# =====================================================================

def classify_severity(ssim_score, damage_pct, yolo_conf=None):
    """
    Phan loai muc do nghiem trong dua tren SSIM + damage% + YOLO confidence.

    | SSIM    | Damage% | Muc do  |
    |---------|---------|---------|
    | > 0.95  | < 2%    | NONE    |
    | > 0.85  | < 5%    | LOW     |
    | > 0.70  | < 15%   | MEDIUM  |
    | <= 0.70 | >= 15%  | HIGH    |
    """
    if ssim_score > 0.95 and damage_pct < 2.0:
        severity = "NONE"
        score = 0.0
    elif ssim_score > 0.85 and damage_pct < 5.0:
        severity = "LOW"
        score = 0.25
    elif ssim_score > 0.70 and damage_pct < 15.0:
        severity = "MEDIUM"
        score = 0.55
    else:
        severity = "HIGH"
        score = 0.85

    # YOLO confidence boost: neu YOLO rat tu tin -> tang severity score
    if yolo_conf is not None and yolo_conf > 0.7:
        score = min(1.0, score + 0.1)

    return severity, score


def classify_region_severity(region_ssim, yolo_conf):
    """Phan loai severity cho 1 vung YOLO detect."""
    # region_ssim thap = khac biet lon = hu hai nang
    if region_ssim > 0.90:
        return "LOW", 0.2
    elif region_ssim > 0.75:
        return "MEDIUM", 0.5
    else:
        return "HIGH", 0.8 + (0.2 * yolo_conf)  # YOLO confident -> score cao hon


# =====================================================================
# VISUALIZATION
# =====================================================================

def draw_results(image, detections, region_ssims=None):
    """Ve ket qua YOLO + SSIM severity len anh."""
    output = image.copy()

    for i, det in enumerate(detections):
        x1, y1, x2, y2 = det["bbox"]
        cls_name = det["class_name"]
        conf = det["confidence"]

        if region_ssims and i < len(region_ssims):
            r_ssim = region_ssims[i]
            severity, _ = classify_region_severity(r_ssim, conf)
            color = SEVERITY_COLORS[severity]
            label = f"{cls_name} {conf:.2f} SSIM:{r_ssim:.2f} [{severity}]"
        else:
            color = (0, 255, 0)
            label = f"{cls_name} {conf:.2f}"

        cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)

        # Label background
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(output, (x1, y1 - th - 6), (x1 + tw, y1), color, -1)
        cv2.putText(output, label, (x1, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return output


# =====================================================================
# PIPELINE CHINH
# =====================================================================

def analyze_pipeline(image_path, reference_path, model_path=None,
                     output_dir="pipeline_output", conf=0.25):
    """
    Pipeline day du: YOLO detect + SSIM analysis.

    Args:
        image_path: Duong dan anh can kiem tra
        reference_path: Duong dan anh goc (chua hu)
        model_path: Duong dan YOLO model (None = chi chay SSIM)
        output_dir: Thu muc xuat ket qua
        conf: YOLO confidence threshold
    """
    os.makedirs(output_dir, exist_ok=True)
    basename = os.path.splitext(os.path.basename(image_path))[0]

    # Load images
    img = cv2.imread(image_path)
    ref = cv2.imread(reference_path)
    if img is None:
        print(f"ERROR: Cannot read {image_path}")
        return None
    if ref is None:
        print(f"ERROR: Cannot read {reference_path}")
        return None

    # Resize to same dimensions
    h, w = ref.shape[:2]
    if img.shape[:2] != (h, w):
        print("Aligning images with SIFT...")
        img_aligned, valid_mask, inliers = align_with_sift(img, ref)
        if inliers < 20:
            print(f"WARNING: Poor alignment ({inliers} inliers). Resizing instead.")
            img_aligned = cv2.resize(img, (w, h))
            valid_mask = None
        else:
            print(f"Aligned OK ({inliers} inliers)")
    else:
        img_aligned = img
        valid_mask = None

    report = {"image": image_path, "reference": reference_path}

    # === STEP 1: SSIM Global ===
    print("\n--- SSIM Analysis ---")
    ssim_result = compute_ssim(img_aligned, ref, valid_mask)
    report["ssim"] = {
        "score": round(ssim_result["ssim_score"], 4),
        "gray": round(ssim_result["ssim_gray"], 4),
        "color": round(ssim_result["ssim_color"], 4),
        "damage_pct": round(ssim_result["damage_pct"], 2),
        "num_regions": ssim_result["num_regions"],
    }

    severity, sev_score = classify_severity(
        ssim_result["ssim_score"], ssim_result["damage_pct"]
    )
    report["ssim"]["severity"] = severity
    report["ssim"]["severity_score"] = round(sev_score, 2)

    print(f"  SSIM Score: {ssim_result['ssim_score']:.4f} "
          f"(gray={ssim_result['ssim_gray']:.4f}, color={ssim_result['ssim_color']:.4f})")
    print(f"  Damage: {ssim_result['damage_pct']:.1f}%, {ssim_result['num_regions']} regions")
    print(f"  Severity: {severity} ({sev_score:.2f})")

    # Save SSIM outputs
    cv2.imwrite(os.path.join(output_dir, f"{basename}_heatmap.jpg"), ssim_result["heatmap"])
    cv2.imwrite(os.path.join(output_dir, f"{basename}_mask.png"), ssim_result["damage_mask"])

    # === STEP 2: YOLO Detection (optional) ===
    detections = []
    region_ssims = []

    if model_path and os.path.exists(model_path):
        print("\n--- YOLO Detection ---")
        model = load_yolo_model(model_path)
        detections = yolo_detect(model, image_path, conf=conf)
        print(f"  Found {len(detections)} damage regions")

        # === STEP 3: SSIM per YOLO region ===
        report["detections"] = []
        for i, det in enumerate(detections):
            x1, y1, x2, y2 = det["bbox"]
            r_ssim = compute_region_ssim(img_aligned, ref, x1, y1, x2, y2)
            region_ssims.append(r_ssim)

            r_severity, r_score = classify_region_severity(r_ssim, det["confidence"])

            det_report = {
                "class": det["class_name"],
                "confidence": round(det["confidence"], 4),
                "bbox": [x1, y1, x2, y2],
                "region_ssim": round(r_ssim, 4),
                "severity": r_severity,
                "severity_score": round(r_score, 2),
            }
            report["detections"].append(det_report)
            print(f"  [{i}] {det['class_name']} conf={det['confidence']:.2f} "
                  f"SSIM={r_ssim:.3f} [{r_severity}]")

    # === STEP 4: Visualization ===
    # Overlay voi YOLO boxes + SSIM severity
    if detections:
        overlay = draw_results(img_aligned, detections, region_ssims)
    else:
        overlay = ssim_result["overlay"]

    cv2.imwrite(os.path.join(output_dir, f"{basename}_result.jpg"), overlay)

    # === STEP 5: Summary ===
    print(f"\n--- Summary ---")
    print(f"  Overall SSIM: {ssim_result['ssim_score']:.4f}")
    print(f"  Overall Severity: {severity}")
    if detections:
        by_class = {}
        for det, rs in zip(detections, region_ssims):
            cls = det["class_name"]
            by_class.setdefault(cls, []).append(rs)
        print(f"  YOLO detections: {len(detections)}")
        for cls, ssims in by_class.items():
            avg = np.mean(ssims)
            print(f"    {cls}: {len(ssims)} regions, avg SSIM={avg:.3f}")
    print(f"\n  Output: {output_dir}/{basename}_*.jpg")

    # Save JSON report
    json_path = os.path.join(output_dir, f"{basename}_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  Report: {json_path}")

    return report


def analyze_batch(image_dir, reference_path, model_path=None,
                  output_dir="pipeline_output", conf=0.25):
    """Phan tich nhieu anh trong 1 thu muc."""
    exts = ('.jpg', '.jpeg', '.png')
    images = sorted(f for f in os.listdir(image_dir)
                    if f.lower().endswith(exts))

    print(f"\nBatch analysis: {len(images)} images")
    print(f"Reference: {reference_path}")
    print(f"Model: {model_path or 'None (SSIM only)'}")
    print("=" * 60)

    all_reports = []
    for img_file in images:
        img_path = os.path.join(image_dir, img_file)
        if os.path.abspath(img_path) == os.path.abspath(reference_path):
            continue
        print(f"\n>>> {img_file}")
        report = analyze_pipeline(img_path, reference_path, model_path,
                                  output_dir, conf)
        if report:
            all_reports.append(report)

    # Batch summary
    if all_reports:
        print(f"\n{'='*60}")
        print(f"BATCH SUMMARY: {len(all_reports)} images analyzed")
        print(f"{'='*60}")
        ssim_scores = [r["ssim"]["score"] for r in all_reports]
        damage_pcts = [r["ssim"]["damage_pct"] for r in all_reports]
        severities = [r["ssim"]["severity"] for r in all_reports]

        print(f"  SSIM: min={min(ssim_scores):.4f}, max={max(ssim_scores):.4f}, "
              f"avg={np.mean(ssim_scores):.4f}")
        print(f"  Damage: min={min(damage_pcts):.1f}%, max={max(damage_pcts):.1f}%, "
              f"avg={np.mean(damage_pcts):.1f}%")
        for sev in ["NONE", "LOW", "MEDIUM", "HIGH"]:
            count = severities.count(sev)
            if count > 0:
                print(f"  {sev}: {count}/{len(all_reports)} images")

        # Save batch report
        batch_json = os.path.join(output_dir, "batch_report.json")
        with open(batch_json, "w", encoding="utf-8") as f:
            json.dump(all_reports, f, indent=2, ensure_ascii=False)
        print(f"\n  Batch report: {batch_json}")

    return all_reports


# =====================================================================
# LEGACY: process_face (giu lai tuong thich code cu)
# =====================================================================

def find_best_reference(images):
    """Tim anh trung tam nhat lam reference."""
    n = len(images)
    sift = cv2.SIFT_create(nfeatures=1000)

    descs = []
    for fname, img in images:
        small = cv2.resize(img, (640, int(640 * img.shape[0] / img.shape[1])))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        _, des = sift.detectAndCompute(gray, None)
        descs.append(des)

    bf = cv2.BFMatcher(cv2.NORM_L2)
    avg_matches = []
    for i in range(n):
        total = count = 0
        for j in range(n):
            if i == j or descs[i] is None or descs[j] is None:
                continue
            matches = bf.knnMatch(descs[i], descs[j], k=2)
            good = sum(1 for p in matches if len(p) == 2 and p[0].distance < 0.7 * p[1].distance)
            total += good
            count += 1
        avg_matches.append(total / max(count, 1))

    return np.argmax(avg_matches), avg_matches


def process_face(face_name, processed_dir, output_dir, model_path=None):
    """Xu ly tat ca anh cua 1 mat co vat (tuong thich code cu)."""
    face_out = os.path.join(output_dir, face_name)
    os.makedirs(face_out, exist_ok=True)

    files = sorted(f for f in os.listdir(processed_dir)
                   if f.startswith(face_name) and f.endswith('.jpg'))

    if len(files) < 3:
        print(f"  [SKIP] {face_name}: chi co {len(files)} anh, can >= 3")
        return

    print(f"\n{'='*60}")
    print(f"Analyzing {face_name}: {len(files)} images")
    print(f"{'='*60}")

    images = []
    for f in files:
        img = cv2.imread(os.path.join(processed_dir, f))
        if img is not None:
            images.append((f, img))

    # Tim reference
    print("  Finding best reference...")
    best_idx, avg_matches = find_best_reference(images)
    ref_fname, ref_img = images[best_idx]
    print(f"  Reference: {ref_fname} (avg matches: {avg_matches[best_idx]:.0f})")

    if max(ref_img.shape[:2]) > 1280:
        scale = 1280 / max(ref_img.shape[:2])
        ref_img = cv2.resize(ref_img, None, fx=scale, fy=scale)

    cv2.imwrite(os.path.join(face_out, "reference.jpg"), ref_img)

    # Load YOLO model neu co
    yolo_model = None
    if model_path and os.path.exists(model_path):
        yolo_model = load_yolo_model(model_path)

    results = []
    for fname, img in images:
        if fname == ref_fname:
            continue

        aligned, valid_mask, inliers = align_with_sift(img, ref_img)
        if inliers < 20:
            print(f"  {fname}: SKIP ({inliers} inliers)")
            continue

        # SSIM
        ssim_res = compute_ssim(aligned, ref_img, valid_mask)

        # YOLO (optional)
        detections = []
        region_ssims = []
        if yolo_model:
            img_path = os.path.join(processed_dir, fname)
            detections = yolo_detect(yolo_model, img_path)
            for det in detections:
                x1, y1, x2, y2 = det["bbox"]
                rs = compute_region_ssim(aligned, ref_img, x1, y1, x2, y2)
                region_ssims.append(rs)

        severity, sev_score = classify_severity(
            ssim_res["ssim_score"], ssim_res["damage_pct"]
        )

        results.append((fname, ssim_res, severity, detections, region_ssims))

        # Save
        base = fname.replace('.jpg', '')
        cv2.imwrite(os.path.join(face_out, f"{base}_heatmap.jpg"), ssim_res["heatmap"])
        cv2.imwrite(os.path.join(face_out, f"{base}_mask.png"), ssim_res["damage_mask"])

        if detections:
            overlay = draw_results(aligned, detections, region_ssims)
        else:
            overlay = ssim_res["overlay"]
        cv2.imwrite(os.path.join(face_out, f"{base}_overlay.jpg"), overlay)

        det_str = f", YOLO: {len(detections)} det" if detections else ""
        print(f"  {fname}: SSIM={ssim_res['ssim_score']:.3f}, "
              f"damage={ssim_res['damage_pct']:.1f}%, "
              f"[{severity}]{det_str}")

    if results:
        scores = [r[1]["ssim_score"] for r in results]
        damages = [r[1]["damage_pct"] for r in results]
        print(f"\n  Summary {face_name}: {len(results)} images")
        print(f"    SSIM: {min(scores):.3f} - {max(scores):.3f} (avg {np.mean(scores):.3f})")
        print(f"    Damage: {min(damages):.1f}% - {max(damages):.1f}% (avg {np.mean(damages):.1f}%)")


# =====================================================================
# CLI
# =====================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLO + SSIM Damage Analysis Pipeline")
    parser.add_argument("--image", help="Anh can kiem tra")
    parser.add_argument("--image_dir", help="Thu muc chua nhieu anh")
    parser.add_argument("--reference", help="Anh goc (chua hu)")
    parser.add_argument("--model", help="YOLO model path (best.pt)")
    parser.add_argument("--output", default="pipeline_output", help="Thu muc output")
    parser.add_argument("--conf", type=float, default=0.25, help="YOLO confidence threshold")
    parser.add_argument("--face", help="Face name (legacy mode: face1, face2...)")
    parser.add_argument("--processed_dir", default="processed", help="Thu muc anh da xu ly (legacy)")
    args = parser.parse_args()

    if args.face:
        # Legacy mode: process_face
        process_face(args.face, args.processed_dir, args.output, args.model)

    elif args.image and args.reference:
        # Single image
        analyze_pipeline(args.image, args.reference, args.model,
                         args.output, args.conf)

    elif args.image_dir and args.reference:
        # Batch
        analyze_batch(args.image_dir, args.reference, args.model,
                      args.output, args.conf)

    else:
        # Default: process all faces (legacy)
        model_path = args.model or "best.pt"
        if not os.path.exists(model_path):
            model_path = None
            print("No YOLO model found, running SSIM only")

        for i in range(1, 6):
            process_face(f"face{i}", args.processed_dir, args.output, model_path)
        print(f"\nAll results saved to {args.output}/")
