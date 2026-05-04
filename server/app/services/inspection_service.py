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
        result = {
            "damage_score": 0.0,
            "ssim": None,
            "heatmap_path": None,
            "auto_description": "Analysis performed.",
            "detections_json": None,
        }
        
        if reference_path is None or not reference_path.exists():
            result["auto_description"] = "No reference image found. Analysis skipped."
            return result

        try:
            import cv2
            import numpy as np
            
            current = cv2.imread(str(current_path))
            reference = cv2.imread(str(reference_path))
            
            if current is None or reference is None:
                result["auto_description"] = "Error: Could not decode images."
                return result

            h, w = reference.shape[:2]
            if current.shape[:2] != (h, w):
                current = cv2.resize(current, (w, h))

            gray_cur = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
            gray_ref = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
            
            diff = cv2.absdiff(gray_ref, gray_cur)
            diff_blur = cv2.GaussianBlur(diff, (5, 5), 0)
            _, mask = cv2.threshold(diff_blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            damage_pct = float(cv2.countNonZero(mask)) / float(h * w) * 100.0
            
            heatmap = cv2.applyColorMap(diff_blur, cv2.COLORMAP_JET)
            overlay = cv2.addWeighted(current, 0.6, heatmap, 0.4, 0)
            
            # Use relative path for URL consistency
            heatmap_filename = f"heatmap_{artifact_id}_{ts_ms}.jpg"
            heatmap_save_path = self._settings.uploads_dir / heatmap_filename
            cv2.imwrite(str(heatmap_save_path), overlay)

            ssim_value = None
            try:
                from skimage.metrics import structural_similarity
                ssim_value = float(structural_similarity(gray_ref, gray_cur, win_size=7))
            except Exception:
                pass

            return {
                "damage_score": damage_pct,
                "ssim": ssim_value,
                "heatmap_path": heatmap_filename,
                "auto_description": f"Auto: {damage_pct:.1f}% change detected.",
                "detections_json": None,
            }
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            result["auto_description"] = f"Analysis failed: {str(e)}"
            return result

    def reset_alignment_counter(self, device_id: str, artifact_id: str) -> None:
        alignment_key = f"{device_id}:{artifact_id}"
        self._alignment_counters.pop(alignment_key, None)
        self._alignment_start_ts.pop(alignment_key, None)
