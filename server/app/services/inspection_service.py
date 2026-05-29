from __future__ import annotations

import json
import time
import logging
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.artifact import (
    Artifact, Image, ImageComparison, ImageType, 
    ComparisonStatus, Alert, AlertLevel, InspectionType, Schedule
)
from app.services.command_service import CommandService
from app.services.model_service import ModelService
from app.services.mqtt_bridge import MqttBridge
from app.services.pose_service import PoseService

logger = logging.getLogger(__name__)

class InspectionService:
    def __init__(
        self,
        settings: Settings,
        pose_service: PoseService,
        model_service: ModelService,
        command_service: CommandService,
        mqtt_bridge: MqttBridge,
    ) -> None:
        self._settings = settings
        self._pose_service = pose_service
        self._model_service = model_service
        self._command_service = command_service
        self._mqtt_bridge = mqtt_bridge
        self._alignment_counters: dict[str, int] = {}
        self._alignment_start_ts: dict[str, float] = {}

    async def _save_file(
        self, file: UploadFile, artifact_id: str | None = None
    ) -> tuple[Path, int]:
        ts_ms = int(time.time() * 1000)
        safe_name = (file.filename or "upload.bin").replace("/", "_").replace("\\", "_")
        if artifact_id and artifact_id.strip():
            target_dir = self._artifact_uploads_dir / artifact_id.strip()
        else:
            target_dir = self._settings.uploads_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{ts_ms}_{safe_name}"
        content = await file.read()
        target_path.write_bytes(content)
        return target_path, len(content)

    @property
    def _artifact_uploads_dir(self) -> Path:
        return self._settings.uploads_dir / "artifacts"

    async def save_reference_image(self, artifact_id: str, file: UploadFile, operator_id: str | None = None) -> Image:
        target_dir = self._artifact_uploads_dir / str(artifact_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        ts_ms = int(time.time() * 1000)
        safe_name = (file.filename or "reference.jpg").replace("/", "_").replace("\\", "_")
        target_path = target_dir / f"reference_{ts_ms}_{safe_name}"
        content = await file.read()
        target_path.write_bytes(content)
        return Image(
            artifact_id=artifact_id,
            operator_id=operator_id,
            image_type=ImageType.baseline,
            image_path=str(target_path),
            is_valid=True
        )

    def run_artifact_inspection(
        self,
        *,
        db: Session,
        artifact: Artifact,
        image_bytes: bytes,
        original_filename: str,
        description: str = "",
        operator_id: str | None = None,
        device_id: str | None = None,
        inspection_type: InspectionType = InspectionType.sudden,
        schedule_id: str | None = None,
        created_by: str | None = None,
    ) -> ImageComparison:
        target_dir = self._artifact_uploads_dir / str(artifact.artifact_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        ts_ms = int(time.time() * 1000)
        safe_name = original_filename.replace("/", "_").replace("\\", "_")
        current_path = target_dir / f"inspection_{ts_ms}_{safe_name}"
        current_path.write_bytes(image_bytes)

        current_image = Image(
            artifact_id=artifact.artifact_id,
            device_id=device_id,
            operator_id=operator_id,
            image_type=ImageType.inspection,
            image_path=str(current_path),
            is_valid=True
        )
        db.add(current_image)
        db.flush()

        reference_path = None
        previous_image_id = None
        if artifact.baseline_image:
            reference_path = Path(artifact.baseline_image.image_path)
            previous_image_id = artifact.baseline_image.image_id
        
        analysis = self._analyze_against_reference(
            current_path=current_path,
            reference_path=reference_path,
            artifact_id=artifact.artifact_id,
            ts_ms=ts_ms,
        )

        damage_score = 0.0
        all_dets = analysis.get("all_detections") or []
        ssim_val = analysis.get("ssim")
        damage_pct = analysis.get("damage_pct")
        status = self._classify_damage_status(all_dets, ssim_val, damage_pct)

        comparison = ImageComparison(
            artifact_id=artifact.artifact_id,
            previous_image_id=previous_image_id or current_image.image_id,
            current_image_id=current_image.image_id,
            schedule_id=schedule_id,
            damage_score=round(damage_pct or 0.0, 2),
            ssim_score=(f"{ssim_val:.4f}" if ssim_val is not None else None),
            heatmap_path=analysis.get("heatmap_path"),
            status=status,
            inspection_type=inspection_type,
            description=description or analysis.get("auto_description", ""),
            detections_json=analysis.get("detections_json"),
            created_by=(created_by or "").strip() or None,
        )
        db.add(comparison)
        db.flush()  # Ensure comparison_id is generated before referencing it in Alert

        if schedule_id:
            sched = db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if sched:
                sched.completed = True

        if status in [ComparisonStatus.warning, ComparisonStatus.damaged]:
            alert_level = AlertLevel.high if status == ComparisonStatus.damaged else AlertLevel.medium
            alert = Alert(
                artifact_id=artifact.artifact_id,
                comparison_id=comparison.comparison_id,
                alert_level=alert_level,
                is_handled=False
            )
            db.add(alert)

        artifact.status = self._merge_artifact_status(artifact.status, status.value)
        db.commit()
        db.refresh(comparison)
        return comparison

    @staticmethod
    def _classify_damage_status(
        detections: list[dict],
        ssim: float | None,
        damage_pct: float | None,
    ) -> ComparisonStatus:
        """Combine SSIM structural similarity with YOLO detections to classify status.

        Priority:
        - If SSIM is available, use it as the primary metric.
        - YOLO HIGH-confidence detections can escalate the status.
        - Without SSIM, fall back to YOLO confidence only.
        """
        # Determine SSIM-based grade
        ssim_status: ComparisonStatus | None = None
        if ssim is not None:
            dpct = damage_pct or 0.0
            if ssim >= 0.95 and dpct < 2.0:
                ssim_status = ComparisonStatus.good
            elif ssim >= 0.85 and dpct < 10.0:
                ssim_status = ComparisonStatus.warning
            else:
                ssim_status = ComparisonStatus.damaged

        # Determine YOLO-based grade
        yolo_status: ComparisonStatus | None = None
        if detections:
            max_conf = max(float(d.get("confidence", 0)) for d in detections)
            if max_conf >= 0.65:
                yolo_status = ComparisonStatus.damaged
            elif max_conf >= 0.40:
                yolo_status = ComparisonStatus.warning
            else:
                yolo_status = ComparisonStatus.good

        # Merge: take the worst result from both signals
        _rank = {ComparisonStatus.good: 0, ComparisonStatus.warning: 1, ComparisonStatus.damaged: 2}
        candidates = [s for s in (ssim_status, yolo_status) if s is not None]
        if not candidates:
            return ComparisonStatus.good
        return max(candidates, key=lambda s: _rank[s])

    @staticmethod
    def _merge_artifact_status(current: str, new_status: str) -> str:
        priority = {"good": 0, "archived": 0, "need_check": 1, "maintenance": 1, "warning": 2, "damaged": 3}
        cur_p = priority.get(current, 0)
        new_p = priority.get(new_status, 0)
        return new_status if new_p > cur_p else current

    def _analyze_against_reference(self, *, current_path: Path, reference_path: Path | None, artifact_id: str, ts_ms: int) -> dict[str, Any]:
        result: dict[str, Any] = {
            "ssim": None,
            "ssim_gray": None,
            "ssim_color": None,
            "damage_pct": None,
            "heatmap_path": None,
            "auto_description": "Analysis performed.",
            "detections_json": None,
            "all_detections": [],
        }

        try:
            import cv2
            import numpy as np
            current_img = cv2.imread(str(current_path))
            if current_img is None:
                result["auto_description"] = "Error: Cannot read inspection image."
                return result
        except Exception as load_exc:
            result["auto_description"] = f"Image load error: {load_exc}"
            return result

        # ── SIFT alignment + full SSIM analysis (requires reference image) ──
        aligned_img: Any = None
        crop_regions: list[dict] = []  # populated in SSIM block, consumed by YOLO block
        if reference_path is not None and reference_path.exists():
            try:
                import numpy as np
                from skimage.metrics import structural_similarity
                reference_img = cv2.imread(str(reference_path))
                if reference_img is not None:
                    h, w = reference_img.shape[:2]
                    cur_resized = cv2.resize(current_img, (w, h)) if current_img.shape[:2] != (h, w) else current_img.copy()

                    # SIFT alignment with valid mask
                    aligned_img, valid_mask, _ = self._sift_align_with_mask(cur_resized, reference_img)

                    # Use aligned result as source for SSIM
                    source = aligned_img if aligned_img is not None else cur_resized

                    # ── Multi-channel SSIM (from analyze_damage.py) ─────────
                    gray_src = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
                    gray_ref = cv2.cvtColor(reference_img, cv2.COLOR_BGR2GRAY)

                    score_gray, diff_gray = structural_similarity(gray_ref, gray_src, full=True, win_size=7)

                    score_channels = []
                    diff_color = np.zeros_like(gray_src, dtype=np.float64)
                    for c in range(3):
                        sc, dc = structural_similarity(
                            reference_img[:, :, c], source[:, :, c], full=True, win_size=7
                        )
                        score_channels.append(sc)
                        diff_color += (1.0 - dc)
                    diff_color /= 3.0
                    score_color = float(np.mean(score_channels))

                    # Combined diff map: max of grayscale and color differences
                    diff_combined = np.maximum(1.0 - diff_gray, diff_color)
                    diff_uint8 = (diff_combined * 255).astype(np.uint8)

                    # Weighted SSIM: grayscale 60% + color 40%
                    ssim_score = 0.6 * float(score_gray) + 0.4 * score_color
                    result["ssim"] = ssim_score
                    result["ssim_gray"] = float(score_gray)
                    result["ssim_color"] = score_color

                    # Apply valid mask (SIFT warp boundary)
                    if valid_mask is not None:
                        diff_uint8 = cv2.bitwise_and(diff_uint8, valid_mask)

                    # ── Heatmap (JET colormap overlay) ─────────────────────
                    heatmap = cv2.applyColorMap(diff_uint8, cv2.COLORMAP_JET)
                    if valid_mask is not None:
                        heatmap[cv2.bitwise_not(valid_mask) > 0] = [128, 128, 128]
                    heatmap_overlay = cv2.addWeighted(source, 0.6, heatmap, 0.4, 0)

                    # ── Damage mask: Otsu adaptive threshold ───────────────
                    blurred = cv2.GaussianBlur(diff_uint8, (5, 5), 0)
                    otsu_thresh, damage_mask = cv2.threshold(
                        blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
                    )
                    if otsu_thresh < 30:
                        _, damage_mask = cv2.threshold(blurred, 60, 255, cv2.THRESH_BINARY)

                    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                    kernel_big  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
                    damage_mask = cv2.morphologyEx(damage_mask, cv2.MORPH_OPEN,  kernel_small, iterations=2)
                    damage_mask = cv2.morphologyEx(damage_mask, cv2.MORPH_CLOSE, kernel_big,   iterations=2)

                    # Contours + damage %
                    contours, _ = cv2.findContours(damage_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    min_area = max(500, (h * w) * 0.0005)
                    big_contours = [c for c in contours if cv2.contourArea(c) > min_area]
                    cv2.drawContours(heatmap_overlay, big_contours, -1, (0, 0, 255), 2)

                    valid_area = int(cv2.countNonZero(valid_mask)) if valid_mask is not None else (h * w)
                    damage_area = sum(cv2.contourArea(c) for c in big_contours)
                    damage_pct = (damage_area / max(valid_area, 1)) * 100.0
                    result["damage_pct"] = round(damage_pct, 2)

                    # ── Crop từng vùng hư hại → đưa vào AI ────────────────
                    # NGƯỠNG tổng thể: chỉ crop khi damage_pct >= 0.5%.
                    #   Dưới ngưỡng này → contour chỉ là nhiễu alignment/ánh sáng, bỏ qua.
                    # NGƯỠNG cấp contour: min_area đã lọc ở trên.
                    # padding=0 vì bbox đã có padding 30% sẵn; không cần double-pad.
                    _crop_dir = self._artifact_uploads_dir / artifact_id
                    _crop_dir.mkdir(parents=True, exist_ok=True)
                    if damage_pct >= 0.5:
                        _sorted_contours = sorted(big_contours, key=cv2.contourArea, reverse=True)
                        for _idx, _contour in enumerate(_sorted_contours):
                            _bx, _by, _bw, _bh = cv2.boundingRect(_contour)
                            _side = max(_bw, _bh)
                            _pad = max(40, int(_side * 0.3))
                            _half = (_side // 2) + _pad
                            _cxc = _bx + _bw // 2
                            _cyc = _by + _bh // 2
                            _x1c = max(0, _cxc - _half)
                            _y1c = max(0, _cyc - _half)
                            _x2c = min(w, _cxc + _half)
                            _y2c = min(h, _cyc + _half)
                            if _x2c - _x1c < 40 or _y2c - _y1c < 40:
                                continue
                            _crop_arr = source[_y1c:_y2c, _x1c:_x2c]
                            _crop_fname = f"crop_{artifact_id}_{ts_ms}_{_idx}.jpg"
                            cv2.imwrite(str(_crop_dir / _crop_fname), _crop_arr)
                            _r_ssim = self._compute_region_ssim(
                                source, reference_img, _x1c, _y1c, _x2c, _y2c, padding=0
                            )
                            crop_regions.append({
                                "index": _idx,
                                "crop_path": f"/uploads/artifacts/{artifact_id}/{_crop_fname}",
                                "region_bbox": [_x1c, _y1c, _x2c, _y2c],
                                "region_ssim": round(float(_r_ssim), 4),
                                "area_pct": round(float(cv2.contourArea(_contour)) / max(valid_area, 1) * 100, 2),
                                "_crop_arr": _crop_arr,  # temp — removed before JSON serialization
                            })

                    # Save heatmap
                    heatmap_filename = f"heatmap_{artifact_id}_{ts_ms}.jpg"
                    heatmap_dir = self._artifact_uploads_dir / artifact_id
                    heatmap_dir.mkdir(parents=True, exist_ok=True)
                    heatmap_full_path = heatmap_dir / heatmap_filename
                    cv2.imwrite(str(heatmap_full_path), heatmap_overlay)
                    result["heatmap_path"] = str(heatmap_full_path)

                    # Save SIFT-aligned image
                    if aligned_img is not None:
                        detect_dir = self._artifact_uploads_dir / artifact_id
                        detect_dir.mkdir(parents=True, exist_ok=True)
                        aligned_filename = f"aligned_{artifact_id}_{ts_ms}.jpg"
                        cv2.imwrite(str(detect_dir / aligned_filename), aligned_img)
                        result["aligned_image_path"] = f"/uploads/artifacts/{artifact_id}/{aligned_filename}"

            except Exception as align_exc:
                logger.error(f"[analyze] SSIM/alignment error: {align_exc}")
        else:
            result["auto_description"] = "No reference image — AI detection only."

        # ── YOLO detection per crop → map bboxes back to original image ─────
        # Nếu có crop_regions (có reference): YOLO chạy trên từng crop,
        #   tọa độ bbox được cộng offset (x1c, y1c) về ảnh gốc.
        # Nếu không có reference (không SSIM): YOLO chạy trên ảnh gốc như thường.
        try:
            _SEVERITY_COLOR = {
                "HIGH":   (0,   0,   255),
                "MEDIUM": (0,   128, 255),
                "LOW":    (0,   200, 128),
            }
            # Annotate trên ảnh đã align (nếu có), để bbox khớp với SSIM diff map
            annotate_base = aligned_img if aligned_img is not None else current_img
            annotated = annotate_base.copy()
            all_dets: list[dict] = []

            if crop_regions:
                # ── Có SSIM crops: chạy YOLO trên từng crop ──────────────
                for _crop in crop_regions:                    _x1c, _y1c, _x2c, _y2c = _crop["region_bbox"]
                    _crop_arr = _crop.pop("_crop_arr", None)
                    if _crop_arr is None:
                        # fallback: đọc lại từ disk (vừa lưu xong)
                        _disk_path = self._artifact_uploads_dir / artifact_id / Path(_crop["crop_path"]).name
                        _crop_arr = cv2.imread(str(_disk_path))
                    if _crop_arr is None:
                        continue

                    # Encode crop → bytes để đưa vào model service
                    _, _enc = cv2.imencode(".jpg", _crop_arr)
                    _crop_dets_raw = self._model_service.detect_image(
                        self._settings.default_ai_model_name,
                        _enc.tobytes(),
                    )
                    _crop_det_list: list[dict] = []
                    for _res in (_crop_dets_raw or []):
                        for _det in _res.get("detections", []):
                            _crop_det_list.append(_det)

                    # Lưu kết quả AI vào từng crop region để Flutter hiển thị
                    _crop["detections"] = [
                        {k: v for k, v in _d.items() if k != "bbox_xyxy"}
                        for _d in _crop_det_list
                    ]

                    # Map tọa độ bbox từ không gian crop → ảnh gốc
                    for _det in _crop_det_list:
                        _cb = [int(v) for v in _det["bbox_xyxy"]]
                        x1 = _x1c + _cb[0]
                        y1 = _y1c + _cb[1]
                        x2 = _x1c + _cb[2]
                        y2 = _y1c + _cb[3]
                        _name = str(_det.get("class_name", "unknown"))
                        _conf = float(_det.get("confidence", 0))
                        _severity = "HIGH" if _conf >= 0.65 else "MEDIUM" if _conf >= 0.40 else "LOW"
                        _color = _SEVERITY_COLOR[_severity]
                        _r_ssim_val = _crop.get("region_ssim")
                        _label = f"{_name} {_conf*100:.0f}%"
                        if _r_ssim_val is not None:
                            _label += f" (SSIM {_r_ssim_val*100:.0f}%)"
                        _thickness = 3 if _severity == "HIGH" else 2
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), _color, _thickness)
                        _fs = 0.50
                        (_tw, _th), _bl = cv2.getTextSize(_label, cv2.FONT_HERSHEY_SIMPLEX, _fs, 1)
                        _yt = max(0, y1 - _th - _bl - 4)
                        cv2.rectangle(annotated, (x1, _yt), (x1 + _tw + 4, y1), _color, -1)
                        cv2.putText(annotated, _label, (x1 + 2, y1 - _bl - 2),
                                    cv2.FONT_HERSHEY_SIMPLEX, _fs, (255, 255, 255), 1, cv2.LINE_AA)
                        all_dets.append({
                            **{k: v for k, v in _det.items() if k != "bbox_xyxy"},
                            "bbox_xyxy": [x1, y1, x2, y2],  # tọa độ ảnh gốc
                            "crop_path": _crop["crop_path"],
                            "crop_region_ssim": _r_ssim_val,
                            "severity": _severity,
                        })
            else:
                # ── Không có crop (damage_pct < 0.5% HOẶC không có reference)
                # → YOLO chạy trên ảnh gốc/aligned như fallback ────────────
                _yolo_raw = self._model_service.detect_image(
                    self._settings.default_ai_model_name,
                    current_path.read_bytes(),
                )
                for _res in (_yolo_raw or []):
                    for _det in _res.get("detections", []):
                        x1, y1, x2, y2 = [int(v) for v in _det["bbox_xyxy"]]
                        _name = str(_det.get("class_name", "unknown"))
                        _conf = float(_det.get("confidence", 0))
                        _severity = "HIGH" if _conf >= 0.65 else "MEDIUM" if _conf >= 0.40 else "LOW"
                        _color = _SEVERITY_COLOR[_severity]
                        _label = f"{_name} {_conf*100:.0f}%"
                        _thickness = 3 if _severity == "HIGH" else 2
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), _color, _thickness)
                        _fs = 0.50
                        (_tw, _th), _bl = cv2.getTextSize(_label, cv2.FONT_HERSHEY_SIMPLEX, _fs, 1)
                        _yt = max(0, y1 - _th - _bl - 4)
                        cv2.rectangle(annotated, (x1, _yt), (x1 + _tw + 4, y1), _color, -1)
                        cv2.putText(annotated, _label, (x1 + 2, y1 - _bl - 2),
                                    cv2.FONT_HERSHEY_SIMPLEX, _fs, (255, 255, 255), 1, cv2.LINE_AA)
                        all_dets.append({**_det, "severity": _severity})

            # Xóa _crop_arr tạm trước khi JSON serialization
            for _cr in crop_regions:
                _cr.pop("_crop_arr", None)

            detect_dir = self._artifact_uploads_dir / artifact_id
            detect_dir.mkdir(parents=True, exist_ok=True)
            detect_filename = f"detect_{artifact_id}_{ts_ms}.jpg"
            cv2.imwrite(str(detect_dir / detect_filename), annotated)
            annotated_url = f"/uploads/artifacts/{artifact_id}/{detect_filename}"

            result["all_detections"] = all_dets
            result["detections_json"] = json.dumps({
                "annotated_path": annotated_url,
                "aligned_path": result.get("aligned_image_path"),
                "all_detections": all_dets,
                "crops": crop_regions,
                "ssim_summary": {
                    "ssim": result.get("ssim"),
                    "ssim_gray": result.get("ssim_gray"),
                    "ssim_color": result.get("ssim_color"),
                    "damage_pct": result.get("damage_pct"),
                } if result.get("ssim") is not None else None,
            })

            det_count = len(all_dets)
            ssim_str = f" | SSIM {result['ssim']*100:.1f}%" if result.get("ssim") is not None else ""
            result["auto_description"] = (
                f"{det_count} region(s) detected{ssim_str}." if det_count
                else f"No damage detected{ssim_str}."
            )

            logger.info("[analyze] %d detection(s), SSIM=%.4f for artifact=%s",
                        det_count, result.get("ssim") or 0.0, artifact_id)
        except Exception as yolo_exc:
            logger.warning(f"[analyze] YOLO detection skipped: {yolo_exc}")

        return result

    @staticmethod
    def _sift_align_with_mask(img: Any, reference: Any) -> tuple[Any, Any, int]:
        """SIFT + Homography alignment. Returns (aligned, valid_mask, inlier_count)."""
        try:
            import cv2
            import numpy as np
            gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray_ref = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)

            sift = cv2.SIFT_create(nfeatures=3000)
            kp1, des1 = sift.detectAndCompute(gray_img, None)
            kp2, des2 = sift.detectAndCompute(gray_ref, None)

            if des1 is None or des2 is None or len(kp1) < 15 or len(kp2) < 15:
                resized = cv2.resize(img, (reference.shape[1], reference.shape[0]))
                return resized, None, 0

            flann = cv2.FlannBasedMatcher({"algorithm": 1, "trees": 5}, {"checks": 50})
            matches = flann.knnMatch(des1, des2, k=2)
            good = [m for pair in matches if len(pair) == 2
                    for m, n in [pair] if m.distance < 0.65 * n.distance]

            if len(good) < 15:
                resized = cv2.resize(img, (reference.shape[1], reference.shape[0]))
                return resized, None, len(good)

            src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            H, inlier_mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 3.0)
            if H is None:
                resized = cv2.resize(img, (reference.shape[1], reference.shape[0]))
                return resized, None, len(good)

            inliers = int(inlier_mask.sum()) if inlier_mask is not None else 0
            h, w = reference.shape[:2]
            aligned = cv2.warpPerspective(img, H, (w, h))

            # Build valid pixel mask (avoid black warped borders)
            ones = np.ones(img.shape[:2], dtype=np.uint8) * 255
            valid_mask = cv2.warpPerspective(ones, H, (w, h))
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
            valid_mask = cv2.erode(valid_mask, kernel, iterations=2)

            return aligned, valid_mask, inliers
        except Exception:
            return None, None, 0

    @staticmethod
    def _compute_region_ssim(img: Any, reference: Any, x1: int, y1: int, x2: int, y2: int, padding: int = 20) -> float:
        """SSIM for a YOLO bounding-box region (with padding). Returns score 0-1."""
        try:
            from skimage.metrics import structural_similarity
            h, w = img.shape[:2]
            px1, py1 = max(0, x1 - padding), max(0, y1 - padding)
            px2, py2 = min(w, x2 + padding), min(h, y2 + padding)
            crop_img = img[py1:py2, px1:px2]
            crop_ref = reference[py1:py2, px1:px2]
            if crop_img.shape[0] < 16 or crop_img.shape[1] < 16:
                return 1.0
            import cv2
            gray_i = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
            gray_r = cv2.cvtColor(crop_ref, cv2.COLOR_BGR2GRAY)
            win = min(7, min(gray_i.shape) - 1)
            if win % 2 == 0:
                win -= 1
            if win < 3:
                return 1.0
            score, _ = structural_similarity(gray_r, gray_i, full=True, win_size=win)
            return float(score)
        except Exception:
            return 1.0

    async def handle_upload(self, file: UploadFile, metadata_str: str) -> dict[str, Any]:
        """Save image uploaded by device agent, run pose correction, record latest metadata."""
        import json as _json
        try:
            meta = _json.loads(metadata_str)
        except Exception as exc:
            raise ValueError(f"Invalid metadata JSON: {exc}") from exc

        device_id = str(meta.get("device_id", ""))
        artifact_id = str(meta.get("artifact_id", ""))
        calibration_data = meta.get("calibration_data", {})

        saved_path, size_bytes = await self._save_file(file, artifact_id=artifact_id or None)

        # Record metadata so the latest capture can be retrieved later
        capture_metadata: dict[str, Any] = {
            "saved_file": saved_path.name,
            "saved_file_full_path": str(saved_path),
            "device_id": device_id,
            "artifact_id": artifact_id,
        }
        if isinstance(calibration_data, dict):
            capture_metadata.update(calibration_data)

        self._command_service.record_latest_capture_metadata(device_id, capture_metadata)

        # Attempt pose correction (non-fatal if it fails)
        pose_result: dict[str, Any] | None = None
        correction_dispatch: dict[str, Any] | None = None
        workflow: dict[str, Any] = calibration_data.get("workflow", {}) if isinstance(calibration_data, dict) else {}
        auto_alignment_loop: bool = isinstance(workflow, dict) and bool(workflow.get("auto_alignment_loop", False))

        # ── Alignment iteration guard ────────────────────────────────────────
        # Each upload during an active alignment loop counts as one iteration.
        # Stop and notify if the limit is exceeded.
        alignment_key = f"{device_id}:{artifact_id}"
        if auto_alignment_loop and device_id:
            self._alignment_counters[alignment_key] = self._alignment_counters.get(alignment_key, 0) + 1
            current_iter = self._alignment_counters[alignment_key]
            max_iter = self._settings.max_alignment_iterations
            capture_metadata["alignment_iteration"] = current_iter
            capture_metadata["alignment_max_iterations"] = max_iter
            self._command_service.record_latest_capture_metadata(device_id, capture_metadata)

            if current_iter > max_iter:
                reason = (
                    f"Alignment did not converge after {max_iter} iterations. "
                    "Please verify the Diamond ArUco marker is clearly visible and well-lit, "
                    "then retry alignment."
                )
                logger.warning(
                    "[alignment] Max iterations exceeded for device=%s artifact=%s (iter=%d/%d)",
                    device_id, artifact_id, current_iter, max_iter,
                )
                capture_metadata["alignment_status"] = "failed"
                capture_metadata["alignment_fail_reason"] = reason
                self._command_service.record_latest_capture_metadata(device_id, capture_metadata)
                self._alignment_counters.pop(alignment_key, None)
                self._alignment_start_ts.pop(alignment_key, None)
                failed_payload: dict[str, Any] = {
                    "action": "alignment_failed",
                    "task_id": self._command_service.build_task_id(),
                    "artifact_id": artifact_id,
                    "device_id": device_id,
                    "reason": reason,
                    "iteration": current_iter,
                    "workflow": workflow,
                }
                self._mqtt_bridge.publish_command(device_id, failed_payload)
                return {
                    "ok": True,
                    "message": f"Alignment stopped: {reason}",
                    "saved_file": saved_path.name,
                    "size_bytes": size_bytes,
                    "pose_result": None,
                    "correction_dispatch": {"status": "alignment_failed", "reason": reason},
                    "ai_result": None,
                }
        else:
            current_iter = 0

        try:
            pose_result = self._pose_service.correct_image(
                saved_path, artifact_id=artifact_id or None
            )
            deviation = pose_result.get("deviation") if pose_result else None

            # Update metadata with pose deviation so Flutter can poll it live
            if deviation:
                capture_metadata["pose_deviation"] = deviation
                self._command_service.record_latest_capture_metadata(device_id, capture_metadata)

            if deviation and not deviation.get("within_tolerance", True):
                # Pose needs correction — dispatch a move command
                motor_cmd = pose_result.get("motor_command")
                if motor_cmd and device_id:
                    # C++ tra ve: move_x (steps, co dau), move_z (steps, co dau),
                    # rotate_pan (do), rotate_tilt (do).
                    # Pi doc: x_steps (duong), x_dir (+1/-1), z_steps (duong), z_dir,
                    # yaw_delta (do), pitch_delta (do).
                    # Can chuyen ten field de tranh Pi nhan lenh nhung khong di chuyen gi.
                    raw_move_x   = float(motor_cmd.get("move_x",      0))
                    raw_move_z   = float(motor_cmd.get("move_z",      0))
                    raw_pan      = float(motor_cmd.get("rotate_pan",  0))
                    raw_tilt     = float(motor_cmd.get("rotate_tilt", 0))
                    mc_payload: dict[str, Any] = {
                        "action": "move",
                        "task_id": self._command_service.build_task_id(),
                        "artifact_id": artifact_id,
                        "x_steps": abs(int(round(raw_move_x))),
                        "x_dir":   1 if raw_move_x >= 0 else -1,
                        "z_steps": abs(int(round(raw_move_z))),
                        "z_dir":   1 if raw_move_z >= 0 else -1,
                        "yaw_delta":   raw_pan,
                        "pitch_delta": raw_tilt,
                        "workflow": workflow,
                    }
                    published, result_info = self._mqtt_bridge.publish_command(device_id, mc_payload)
                    correction_dispatch = {
                        "status": "published" if published else "queued",
                        "info": result_info,
                        "alignment_iteration": current_iter,
                    }
                    if auto_alignment_loop:
                        capture_metadata["alignment_status"] = "correcting"
                        self._command_service.record_latest_capture_metadata(device_id, capture_metadata)
            elif auto_alignment_loop and device_id:
                if deviation is None:
                    # Diamond/marker not detected — retry capture (still within iteration budget)
                    logger.warning(
                        "[alignment] No Diamond ArUco detected for device=%s (iter=%d/%d), retrying",
                        device_id, current_iter, self._settings.max_alignment_iterations,
                    )
                    capture_metadata["alignment_status"] = "no_diamond"
                    self._command_service.record_latest_capture_metadata(device_id, capture_metadata)
                    retry_payload: dict[str, Any] = {
                        "action": "capture",
                        "task_id": self._command_service.build_task_id(),
                        "artifact_id": artifact_id,
                        "capture_job": calibration_data.get("capture_job", "alignment") if isinstance(calibration_data, dict) else "alignment",
                        "basename": f"align_retry_{artifact_id}_{int(time.time() * 1000)}",
                        "workflow": workflow,
                    }
                    published, result_info = self._mqtt_bridge.publish_command(device_id, retry_payload)
                    correction_dispatch = {
                        "status": "retry_capture_published" if published else "retry_capture_failed",
                        "info": result_info,
                    }
                else:
                    # within_tolerance=True — alignment complete, save final aligned image
                    logger.info(
                        "[alignment] Pose within tolerance for device=%s artifact=%s (iter=%d)",
                        device_id, artifact_id, current_iter,
                    )
                    self._alignment_counters.pop(alignment_key, None)
                    self._alignment_start_ts.pop(alignment_key, None)

                    # Copy last captured image to distinctive final_aligned filename
                    if artifact_id:
                        ts_final = int(time.time() * 1000)
                        final_dir = self._artifact_uploads_dir / str(artifact_id)
                        final_dir.mkdir(parents=True, exist_ok=True)
                        final_path = final_dir / f"final_aligned_{artifact_id}_{ts_final}.png"
                        final_path.write_bytes(saved_path.read_bytes())
                        capture_metadata["final_aligned_path"] = str(final_path)
                        logger.info("[alignment] Saved final aligned image: %s", final_path.name)

                    capture_metadata["alignment_status"] = "complete"
                    capture_metadata["alignment_total_iterations"] = current_iter
                    self._command_service.record_latest_capture_metadata(device_id, capture_metadata)

                    complete_payload: dict[str, Any] = {
                        "action": "alignment_complete",
                        "task_id": self._command_service.build_task_id(),
                        "artifact_id": artifact_id,
                        "device_id": device_id,
                        "deviation": deviation,
                        "total_iterations": current_iter,
                        "workflow": workflow,
                    }
                    published, result_info = self._mqtt_bridge.publish_command(device_id, complete_payload)
                    correction_dispatch = {
                        "status": "alignment_complete_published" if published else "alignment_complete_failed",
                        "info": result_info,
                    }
        except Exception as exc:
            logger.warning("Pose correction skipped for device=%s: %s", device_id, exc)
            if auto_alignment_loop and device_id:
                reason = str(exc)
                capture_metadata["alignment_status"] = "failed"
                capture_metadata["alignment_fail_reason"] = reason
                self._command_service.record_latest_capture_metadata(device_id, capture_metadata)
                self._alignment_counters.pop(alignment_key, None)
                self._alignment_start_ts.pop(alignment_key, None)
                # Notify device that alignment failed so it stops immediately
                exc_failed_payload: dict[str, Any] = {
                    "action": "alignment_failed",
                    "task_id": self._command_service.build_task_id(),
                    "artifact_id": artifact_id,
                    "device_id": device_id,
                    "reason": reason,
                    "workflow": workflow,
                }
                self._mqtt_bridge.publish_command(device_id, exc_failed_payload)

        return {
            "ok": True,
            "message": "Uploaded successfully",
            "saved_file": saved_path.name,
            "size_bytes": size_bytes,
            "pose_result": pose_result,
            "correction_dispatch": correction_dispatch,
            "ai_result": None,
        }

    def reset_alignment_counter(self, device_id: str, artifact_id: str) -> None:
        alignment_key = f"{device_id}:{artifact_id}"
        self._alignment_counters.pop(alignment_key, None)
        self._alignment_start_ts.pop(alignment_key, None)
