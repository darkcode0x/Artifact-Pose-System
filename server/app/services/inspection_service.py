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

    async def _save_file(self, file: UploadFile) -> tuple[Path, int]:
        ts_ms = int(time.time() * 1000)
        safe_name = (file.filename or "upload.bin").replace("/", "_").replace("\\", "_")
        target_path = self._settings.uploads_dir / f"{ts_ms}_{safe_name}"
        target_path.parent.mkdir(parents=True, exist_ok=True)
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

        damage_score = float(analysis.get("damage_score", 0.0))
        status = self._classify_damage_status(damage_score, analysis.get("ssim"))

        comparison = ImageComparison(
            artifact_id=artifact.artifact_id,
            previous_image_id=previous_image_id or current_image.image_id,
            current_image_id=current_image.image_id,
            schedule_id=schedule_id,
            damage_score=damage_score,
            ssim_score=(f"{analysis['ssim']:.4f}" if analysis.get("ssim") is not None else None),
            heatmap_path=analysis.get("heatmap_path"),
            status=status,
            inspection_type=inspection_type,
            description=description or analysis.get("auto_description", ""),
            detections_json=analysis.get("detections_json"),
            created_by=(created_by or "").strip() or None,
        )
        db.add(comparison)
        
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
    def _classify_damage_status(damage_score: float, ssim: float | None) -> ComparisonStatus:
        if ssim is not None and ssim > 0.95 and damage_score < 5:
            return ComparisonStatus.good
        if damage_score < 15 and (ssim is None or ssim > 0.85):
            return ComparisonStatus.good
        if damage_score < 35:
            return ComparisonStatus.warning
        return ComparisonStatus.damaged

    @staticmethod
    def _merge_artifact_status(current: str, new_status: str) -> str:
        priority = {"good": 0, "archived": 0, "need_check": 1, "maintenance": 1, "warning": 2, "damaged": 3}
        cur_p = priority.get(current, 0)
        new_p = priority.get(new_status, 0)
        return new_status if new_p > cur_p else current

    def _analyze_against_reference(self, *, current_path: Path, reference_path: Path | None, artifact_id: str, ts_ms: int) -> dict[str, Any]:
        result: dict[str, Any] = {
            "damage_score": 0.0,
            "ssim": None,
            "heatmap_path": None,
            "auto_description": "Analysis performed.",
            "detections_json": None,
        }

        # Load current image once for all analysis
        try:
            import cv2
            import numpy as np
            current_img = cv2.imread(str(current_path))
            if current_img is None:
                result["auto_description"] = "Lỗi: Không đọc được ảnh kiểm tra."
                return result
        except Exception as load_exc:
            result["auto_description"] = f"Lỗi load ảnh: {load_exc}"
            return result

        # ── SSIM + Heatmap (requires reference image) ────────────────────────
        if reference_path is not None and reference_path.exists():
            try:
                reference_img = cv2.imread(str(reference_path))
                if reference_img is not None:
                    h, w = reference_img.shape[:2]
                    cur_cmp = cv2.resize(current_img, (w, h)) if current_img.shape[:2] != (h, w) else current_img.copy()

                    gray_cur = cv2.cvtColor(cur_cmp, cv2.COLOR_BGR2GRAY)
                    gray_ref = cv2.cvtColor(reference_img, cv2.COLOR_BGR2GRAY)

                    diff = cv2.absdiff(gray_ref, gray_cur)
                    diff_blur = cv2.GaussianBlur(diff, (5, 5), 0)

                    heatmap_overlay = cv2.addWeighted(cur_cmp, 0.6, cv2.applyColorMap(diff_blur, cv2.COLORMAP_JET), 0.4, 0)
                    heatmap_filename = f"heatmap_{artifact_id}_{ts_ms}.jpg"
                    cv2.imwrite(str(self._settings.uploads_dir / heatmap_filename), heatmap_overlay)
                    result["heatmap_path"] = heatmap_filename

                    # Compute SSIM first, then derive damage_score from it.
                    # SSIM is the primary metric: 0.9595 → damage = (1-0.9595)*100 = 4.05%
                    # This avoids Otsu threshold inflating the score on minor lighting changes.
                    try:
                        from skimage.metrics import structural_similarity
                        ssim_val = float(structural_similarity(gray_ref, gray_cur, win_size=7))
                        result["ssim"] = ssim_val
                        damage_pct = max(0.0, (1.0 - ssim_val) * 100.0)
                    except Exception:
                        # Fallback: mean normalised pixel diff (gentler than Otsu)
                        damage_pct = float(np.mean(diff_blur)) / 255.0 * 100.0

                    result["damage_score"] = damage_pct
                    result["auto_description"] = f"SSIM: {result.get('ssim', 0):.4f} → {damage_pct:.1f}% sai lệch."
            except Exception as ssim_exc:
                logger.error(f"[analyze] SSIM/heatmap error: {ssim_exc}")
        else:
            result["auto_description"] = "Chưa có ảnh tham chiếu — chỉ AI detect."

        # ── YOLO detection + annotated image (always runs) ───────────────────
        try:
            yolo_result = self._model_service.detect_image(
                self._settings.default_ai_model_name,
                current_path.read_bytes(),
            )

            # Draw bboxes — severity-based coloring matching analyze_damage.py
            # Severity:  HIGH ≥0.65 red,  MEDIUM ≥0.40 orange,  LOW green
            _SEVERITY_COLOR = {
                "HIGH":   (0,   0,   255),  # đỏ
                "MEDIUM": (0,   128, 255),  # cam
                "LOW":    (0,   200, 128),  # xanh lá
            }
            _CLS_VN = {
                "material_loss": "Mat vat lieu", "peel": "Bong troc",
                "scratch": "Tray xuoc", "fold": "Gap/meo",
                "writing_marks": "Vet viet", "dirt": "Ban",
                "staning": "Vet o", "burn_marks": "Vet chay",
            }
            annotated = current_img.copy()
            for res_item in (yolo_result or []):
                for det in res_item.get("detections", []):
                    x1, y1, x2, y2 = [int(v) for v in det["bbox_xyxy"]]
                    name = str(det.get("class_name", "?"))
                    conf = float(det.get("confidence", 0))
                    if conf >= 0.65:
                        severity = "HIGH"
                    elif conf >= 0.40:
                        severity = "MEDIUM"
                    else:
                        severity = "LOW"
                    color = _SEVERITY_COLOR[severity]
                    vn_name = _CLS_VN.get(name, name)
                    label = f"{vn_name} {conf*100:.0f}% [{severity}]"
                    thickness = 3 if severity == "HIGH" else 2
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)
                    font_scale = 0.55
                    (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
                    y_top = max(0, y1 - th - baseline - 4)
                    cv2.rectangle(annotated, (x1, y_top), (x1 + tw + 4, y1), color, -1)
                    cv2.putText(annotated, label, (x1 + 2, y1 - baseline - 2),
                                cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1, cv2.LINE_AA)

            detect_dir = self._artifact_uploads_dir / artifact_id
            detect_dir.mkdir(parents=True, exist_ok=True)
            detect_filename = f"detect_{artifact_id}_{ts_ms}.jpg"
            cv2.imwrite(str(detect_dir / detect_filename), annotated)
            annotated_url = f"/uploads/artifacts/{artifact_id}/{detect_filename}"

            result["detections_json"] = json.dumps({
                "annotated_path": annotated_url,
                "results": yolo_result,
            })

            # ── YOLO-based damage score ───────────────────────────────────────
            # Compute from bbox area × confidence so detections always contribute
            # to damage_score even when there is no reference image.
            all_dets = [d for r in (yolo_result or []) for d in r.get("detections", [])]
            if all_dets:
                h_img, w_img = current_img.shape[:2]
                total_area = max(1, h_img * w_img)
                yolo_score = 0.0
                for det in all_dets:
                    x1, y1, x2, y2 = [int(v) for v in det["bbox_xyxy"]]
                    bbox_area = max(0, x2 - x1) * max(0, y2 - y1)
                    area_pct = (bbox_area / total_area) * 100.0
                    conf = float(det.get("confidence", 0))
                    # Each detection contributes: confidence × sqrt(area%), scaled up
                    yolo_score += conf * (area_pct ** 0.5) * 10.0
                yolo_score = min(100.0, yolo_score)
                # Use max so SSIM-based score isn't overwritten if it's higher
                result["damage_score"] = max(result["damage_score"], yolo_score)
                logger.info(
                    "[analyze] YOLO damage score=%.1f from %d detection(s) for artifact=%s",
                    yolo_score, len(all_dets), artifact_id,
                )
        except Exception as yolo_exc:
            logger.warning(f"[analyze] YOLO detection skipped: {yolo_exc}")

        return result

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

        saved_path, size_bytes = await self._save_file(file)

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
        try:
            pose_result = self._pose_service.correct_image(saved_path)
            deviation = pose_result.get("deviation") if pose_result else None

            # Update metadata with pose deviation so Flutter can poll it live
            if deviation:
                capture_metadata["pose_deviation"] = deviation
                self._command_service.record_latest_capture_metadata(device_id, capture_metadata)

            if deviation and not deviation.get("within_tolerance", True):
                # Pose needs correction — dispatch a move command
                motor_cmd = pose_result.get("motor_command")
                if motor_cmd and device_id:
                    mc_payload: dict[str, Any] = {
                        "action": "move",
                        "task_id": self._command_service.build_task_id(),
                        "artifact_id": artifact_id,
                        **motor_cmd,
                        "workflow": workflow,
                    }
                    published, result_info = self._mqtt_bridge.publish_command(device_id, mc_payload)
                    correction_dispatch = {
                        "status": "published" if published else "queued",
                        "info": result_info,
                    }
            elif auto_alignment_loop and device_id:
                if deviation is None:
                    # Diamond/marker not detected — retry capture
                    logger.warning(f"[alignment] No pose detected for device={device_id}, retrying capture")
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
                    logger.info(f"[alignment] Pose within tolerance for device={device_id}, artifact={artifact_id}")

                    # Copy last captured image to distinctive final_aligned filename
                    if artifact_id:
                        ts_final = int(time.time() * 1000)
                        final_dir = self._artifact_uploads_dir / str(artifact_id)
                        final_dir.mkdir(parents=True, exist_ok=True)
                        final_path = final_dir / f"final_aligned_{artifact_id}_{ts_final}.png"
                        final_path.write_bytes(saved_path.read_bytes())
                        capture_metadata["final_aligned_path"] = str(final_path)
                        self._command_service.record_latest_capture_metadata(device_id, capture_metadata)
                        logger.info(f"[alignment] Saved final aligned image: {final_path.name}")

                    complete_payload: dict[str, Any] = {
                        "action": "alignment_complete",
                        "task_id": self._command_service.build_task_id(),
                        "artifact_id": artifact_id,
                        "device_id": device_id,
                        "deviation": deviation,
                        "workflow": workflow,
                    }
                    published, result_info = self._mqtt_bridge.publish_command(device_id, complete_payload)
                    correction_dispatch = {
                        "status": "alignment_complete_published" if published else "alignment_complete_failed",
                        "info": result_info,
                    }
        except Exception as exc:
            logger.warning(f"Pose correction skipped for device={device_id}: {exc}")
            if auto_alignment_loop and device_id:
                # Notify device that alignment failed so it stops waiting
                failed_payload: dict[str, Any] = {
                    "action": "alignment_failed",
                    "task_id": self._command_service.build_task_id(),
                    "artifact_id": artifact_id,
                    "device_id": device_id,
                    "reason": str(exc),
                    "workflow": workflow,
                }
                self._mqtt_bridge.publish_command(device_id, failed_payload)

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
