from __future__ import annotations

import json
import time
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
        # Track alignment loop iterations per (device_id, artifact_id).
        self._alignment_counters: dict[str, int] = {}
        self._alignment_start_ts: dict[str, float] = {}

    async def handle_upload(self, file: UploadFile, metadata_json: str) -> dict[str, Any]:
        metadata = self._parse_metadata(metadata_json)
        capture_payload = self._extract_capture_payload(metadata)
        device_id = self._extract_device_id(metadata, capture_payload)
        artifact_id = self._extract_artifact_id(metadata, capture_payload)

        target_path, size_bytes = await self._save_file(file)

        if device_id:
            self._record_latest_capture_metadata(
                device_id=device_id,
                artifact_id=artifact_id,
                capture_payload=capture_payload,
                source_metadata=metadata,
            )

        pose_result: dict[str, Any] | None = None
        correction_dispatch: dict[str, Any] | None = None
        if self._settings.run_pose_on_upload:
            try:
                pose_result = self._pose_service.correct_image(target_path)
            except Exception as exc:
                pose_result = {
                    "ok": False,
                    "error": str(exc),
                }

            if self._settings.auto_dispatch_pose_command and pose_result is not None:
                correction_dispatch = self._dispatch_pose_command(
                    metadata=metadata,
                    capture_payload=capture_payload,
                    device_id=device_id,
                    artifact_id=artifact_id,
                    pose_result=pose_result,
                )

        ai_result: dict[str, Any] | None = None
        if self._settings.run_ai_on_upload:
            ai_result = self._run_ai(metadata)

        record = {
            "timestamp_ms": int(time.time() * 1000),
            "saved_file": str(target_path),
            "metadata": metadata,
            "content_type": file.content_type,
            "size_bytes": size_bytes,
            "pose_result": pose_result,
            "correction_dispatch": correction_dispatch,
            "ai_result": ai_result,
        }
        self._append_log(record)

        return {
            "ok": True,
            "message": "Upload received",
            "saved_file": str(target_path),
            "size_bytes": size_bytes,
            "pose_result": pose_result,
            "correction_dispatch": correction_dispatch,
            "ai_result": ai_result,
        }

    @staticmethod
    def _parse_metadata(metadata_json: str) -> dict[str, Any]:
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid metadata JSON: {exc}") from exc

        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a JSON object")

        return metadata

    @staticmethod
    def _extract_capture_payload(metadata: dict[str, Any]) -> dict[str, Any]:
        calibration = metadata.get("calibration_data")
        if isinstance(calibration, dict):
            return calibration
        return {}

    @staticmethod
    def _extract_device_id(metadata: dict[str, Any], capture_payload: dict[str, Any]) -> str:
        raw = metadata.get("device_id")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()

        raw = capture_payload.get("device_id")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()

        return ""

    @staticmethod
    def _extract_artifact_id(metadata: dict[str, Any], capture_payload: dict[str, Any]) -> str:
        raw = metadata.get("artifact_id")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()

        raw = capture_payload.get("artifact_id")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()

        return "artifact_demo_001"

    def _record_latest_capture_metadata(
        self,
        device_id: str,
        artifact_id: str,
        capture_payload: dict[str, Any],
        source_metadata: dict[str, Any],
    ) -> None:
        capture_job = str(capture_payload.get("capture_job", "unknown"))
        latest_record = {
            "device_id": device_id,
            "artifact_id": artifact_id,
            "capture_job": capture_job,
            "camera_runtime_metadata": capture_payload.get("camera_runtime_metadata"),
            "camera_static_params": capture_payload.get("camera_static_params"),
            "workflow": capture_payload.get("workflow", {}),
            "saved_ts_ms": int(time.time() * 1000),
            "source_metadata": {
                "artifact_id": source_metadata.get("artifact_id"),
                "device_id": source_metadata.get("device_id"),
            },
        }
        self._command_service.record_latest_capture_metadata(device_id, latest_record)

    async def _save_file(self, file: UploadFile) -> tuple[Path, int]:
        ts_ms = int(time.time() * 1000)
        safe_name = (file.filename or "upload.bin").replace("/", "_").replace("\\", "_")
        target_path = self._settings.uploads_dir / f"{ts_ms}_{safe_name}"
        target_path.parent.mkdir(parents=True, exist_ok=True)

        content = await file.read()
        target_path.write_bytes(content)
        return target_path, len(content)

    def _append_log(self, record: dict[str, Any]) -> None:
        with self._settings.inspections_log_file.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _run_ai(self, metadata: dict[str, Any]) -> dict[str, Any] | None:
        model_name = metadata.get("model_name")
        ai_input = metadata.get("ai_input")

        if not model_name:
            return {
                "ok": False,
                "error": "model_name is missing in metadata",
            }

        if ai_input is None:
            return {
                "ok": False,
                "error": "ai_input is missing in metadata",
            }

        try:
            output = self._model_service.predict(str(model_name), ai_input)
            return {
                "ok": True,
                "model_name": str(model_name),
                "output": output,
            }
        except Exception as exc:
            return {
                "ok": False,
                "model_name": str(model_name),
                "error": str(exc),
            }

    def _dispatch_pose_command(
        self,
        metadata: dict[str, Any],
        capture_payload: dict[str, Any],
        device_id: str,
        artifact_id: str,
        pose_result: dict[str, Any],
    ) -> dict[str, Any]:
        if not device_id:
            return {
                "ok": False,
                "sent": False,
                "reason": "missing_device_id",
            }

        capture_job = str(capture_payload.get("capture_job", "alignment")).lower()
        if capture_job != "alignment":
            return {
                "ok": True,
                "sent": False,
                "reason": f"capture_job_{capture_job}_no_dispatch",
            }

        alignment_key = f"{device_id}:{artifact_id}"

        if pose_result.get("deviation") is None:
            return {
                "ok": False,
                "sent": False,
                "reason": "missing_deviation",
            }

        deviation = pose_result.get("deviation") or {}

        # --- Check within_tolerance → send alignment_complete signal ---
        if bool(deviation.get("within_tolerance", False)):
            self._alignment_counters.pop(alignment_key, None)
            self._alignment_start_ts.pop(alignment_key, None)
            self._publish_alignment_signal(
                device_id=device_id,
                action="alignment_complete",
                deviation=deviation,
                artifact_id=artifact_id,
            )
            return {
                "ok": True,
                "sent": False,
                "reason": "within_tolerance",
                "signal_sent": "alignment_complete",
            }

        # --- Check loop limits ---
        iteration = self._alignment_counters.get(alignment_key, 0) + 1
        start_ts = self._alignment_start_ts.get(alignment_key)
        now = time.time()
        if start_ts is None:
            start_ts = now
            self._alignment_start_ts[alignment_key] = start_ts

        if iteration > self._settings.max_alignment_iterations:
            self._alignment_counters.pop(alignment_key, None)
            self._alignment_start_ts.pop(alignment_key, None)
            self._publish_alignment_signal(
                device_id=device_id,
                action="alignment_failed",
                deviation=deviation,
                artifact_id=artifact_id,
                reason=f"max_iterations_exceeded ({self._settings.max_alignment_iterations})",
                iteration=iteration - 1,
            )
            return {
                "ok": False,
                "sent": False,
                "reason": "max_iterations_exceeded",
                "iteration": iteration - 1,
                "signal_sent": "alignment_failed",
            }

        elapsed = now - start_ts
        if elapsed > self._settings.alignment_timeout_sec:
            self._alignment_counters.pop(alignment_key, None)
            self._alignment_start_ts.pop(alignment_key, None)
            self._publish_alignment_signal(
                device_id=device_id,
                action="alignment_failed",
                deviation=deviation,
                artifact_id=artifact_id,
                reason=f"timeout ({self._settings.alignment_timeout_sec}s)",
                iteration=iteration - 1,
            )
            return {
                "ok": False,
                "sent": False,
                "reason": "alignment_timeout",
                "elapsed_sec": round(elapsed, 1),
                "signal_sent": "alignment_failed",
            }

        self._alignment_counters[alignment_key] = iteration

        motor_command = pose_result.get("motor_command") or deviation.get("motor_command") or {}
        if not isinstance(motor_command, dict):
            return {
                "ok": False,
                "sent": False,
                "reason": "invalid_motor_command",
            }

        # Raw values from C++ deviation calculator
        raw_move_x = float(motor_command.get("move_x", 0.0) or 0.0)
        raw_move_z = float(motor_command.get("move_z", 0.0) or 0.0)
        raw_rotate_pan = float(motor_command.get("rotate_pan", 0.0) or 0.0)
        raw_rotate_tilt = float(motor_command.get("rotate_tilt", 0.0) or 0.0)

        # Apply configurable sign multipliers (default -1 = negate deviation for correction)
        move_x = raw_move_x * self._settings.sign_move_x
        move_z = raw_move_z * self._settings.sign_move_z
        rotate_pan = raw_rotate_pan * self._settings.sign_rotate_pan
        rotate_tilt = raw_rotate_tilt * self._settings.sign_rotate_tilt

        print(
            f"[POSE_DISPATCH] iter={iteration} "
            f"raw: x={raw_move_x:.1f} z={raw_move_z:.1f} pan={raw_rotate_pan:.3f} tilt={raw_rotate_tilt:.3f} | "
            f"signs: x={self._settings.sign_move_x} z={self._settings.sign_move_z} "
            f"pan={self._settings.sign_rotate_pan} tilt={self._settings.sign_rotate_tilt} | "
            f"final: x={move_x:.1f} z={move_z:.1f} pan={rotate_pan:.3f} tilt={rotate_tilt:.3f}"
        )

        movement_steps: list[dict[str, Any]] = []
        if abs(rotate_pan) > 1e-9:
            movement_steps.append({"axis": "pan", "delta": rotate_pan})
        if abs(rotate_tilt) > 1e-9:
            movement_steps.append({"axis": "tilt", "delta": rotate_tilt})
        if abs(move_x) > 1e-9:
            movement_steps.append(
                {
                    "axis": "slider_x",
                    "steps": int(abs(round(move_x))) * (1 if move_x >= 0 else -1),
                }
            )
        if abs(move_z) > 1e-9:
            movement_steps.append(
                {
                    "axis": "slider_z",
                    "steps": int(abs(round(move_z))) * (1 if move_z >= 0 else -1),
                }
            )

        payload = {
            "action": "move",
            "task_id": self._command_service.build_task_id(),
            "yaw_delta": rotate_pan,
            "pitch_delta": rotate_tilt,
            "x_steps": int(abs(round(move_x))),
            "z_steps": int(abs(round(move_z))),
            "x_dir": 1 if move_x >= 0 else -1,
            "z_dir": 1 if move_z >= 0 else -1,
            "movement_steps": movement_steps,
            "workflow": {
                "auto_alignment_loop": True,
                "capture_job": "alignment",
                "source": "g2o_correction",
            },
            "capture_after_move": self._build_capture_after_move(
                capture_payload=capture_payload,
                artifact_id=artifact_id,
            ),
            "source": "g2o_correction",
        }

        published, result = self._mqtt_bridge.publish_command(device_id, payload)
        queued = 0
        mode = "mqtt"

        if not published:
            queued = self._command_service.queue_command(device_id, payload)
            mode = "http_queue_fallback"

        return {
            "ok": True,
            "sent": True,
            "mode": mode,
            "device_id": device_id,
            "task_id": payload["task_id"],
            "published": published,
            "topic": result if published else None,
            "publish_error": None if published else result,
            "queued": queued,
            "payload": payload,
        }

    def _build_capture_after_move(
        self,
        capture_payload: dict[str, Any],
        artifact_id: str,
    ) -> dict[str, Any]:
        static_params = capture_payload.get("camera_static_params")
        runtime_params = capture_payload.get("camera_runtime_metadata")
        if not isinstance(static_params, dict):
            static_params = {}
        if not isinstance(runtime_params, dict):
            runtime_params = {}

        capture_after_move: dict[str, Any] = {
            "enabled": True,
            "capture_job": "alignment",
            "artifact_id": artifact_id,
            "basename_prefix": "align_loop",
        }

        lens_position = self._pick_float(
            runtime_params.get("autofocus_lens_position"),
            runtime_params.get("applied_lens_position"),
            static_params.get("lens_position"),
        )
        if lens_position is not None:
            capture_after_move["lens_position"] = lens_position

        for key in (
            "autofocus_mode",
            "awbgains",
            "gain",
            "shutter",
            "pre_set_controls_delay_sec",
            "pre_capture_request_delay_sec",
            "autofocus_probe_sec",
        ):
            if key in static_params:
                capture_after_move[key] = static_params[key]

        return capture_after_move

    @staticmethod
    def _pick_float(*values: Any) -> float | None:
        for value in values:
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    def reset_alignment_counter(self, device_id: str, artifact_id: str) -> None:
        """Reset loop counter khi bat dau alignment moi."""
        alignment_key = f"{device_id}:{artifact_id}"
        self._alignment_counters.pop(alignment_key, None)
        self._alignment_start_ts.pop(alignment_key, None)

    # ================================================================
    # ARTIFACT-CENTRIC INSPECTION (used by /api/v1/artifacts routes)
    # ================================================================

    @property
    def _artifact_uploads_dir(self) -> Path:
        return self._settings.uploads_dir / "artifacts"

    async def save_reference_image(self, artifact_id: int, file: UploadFile, operator_id: int | None = None) -> Image:
        """Persist a reference image for an artifact and create an Image record."""
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
            image_type=ImageType.BASELINE,
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
        operator_id: int | None = None,
        device_id: int | None = None,
        inspection_type: InspectionType = InspectionType.SUDDEN,
        schedule_id: int | None = None,
        created_by: str | None = None,
    ) -> ImageComparison:
        """
        Save the new image, compare with the artifact's reference, persist an
        Image record and an ImageComparison record.
        """
        target_dir = self._artifact_uploads_dir / str(artifact.artifact_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        ts_ms = int(time.time() * 1000)
        safe_name = original_filename.replace("/", "_").replace("\\", "_")
        current_path = target_dir / f"inspection_{ts_ms}_{safe_name}"
        current_path.write_bytes(image_bytes)

        # Create Image record for current capture
        current_image = Image(
            artifact_id=artifact.artifact_id,
            device_id=device_id,
            operator_id=operator_id,
            image_type=ImageType.INSPECTION,
            image_path=str(current_path),
            is_valid=True
        )
        db.add(current_image)
        db.flush()

        # Get baseline image path
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

        damage_score = float(analysis["damage_score"])
        status = self._classify_damage_status(damage_score, analysis.get("ssim"))

        # Create Comparison
        comparison = ImageComparison(
            artifact_id=artifact.artifact_id,
            previous_image_id=previous_image_id or current_image.image_id,
            current_image_id=current_image.image_id,
            schedule_id=schedule_id,
            damage_score=damage_score,
            ssim_score=(
                f"{analysis['ssim']:.4f}" if analysis.get("ssim") is not None else None
            ),
            heatmap_path=analysis.get("heatmap_path"),
            status=status,
            inspection_type=inspection_type,
            description=description or analysis.get("auto_description", ""),
            detections_json=analysis.get("detections_json"),
            created_by=(created_by or "").strip() or None,
        )
        db.add(comparison)
        
        # If this is a scheduled inspection, mark the schedule as completed
        if schedule_id:
            schedule = db.query(Schedule).get(schedule_id)
            if schedule:
                schedule.completed = True

        db.flush()

        # Handle Alerts
        if status in [ComparisonStatus.WARNING, ComparisonStatus.DAMAGED]:
            alert_level = AlertLevel.HIGH if status == ComparisonStatus.DAMAGED else AlertLevel.MEDIUM
            alert = Alert(
                artifact_id=artifact.artifact_id,
                comparison_id=comparison.comparison_id,
                alert_level=alert_level,
                is_handled=False
            )
            db.add(alert)

        # Update artifact status
        artifact.status = self._merge_artifact_status(artifact.status, status.value)
        db.commit()
        db.refresh(comparison)
        return comparison

    @staticmethod
    def _classify_damage_status(damage_score: float, ssim: float | None) -> ComparisonStatus:
        if ssim is not None and ssim > 0.95 and damage_score < 5:
            return ComparisonStatus.GOOD
        if damage_score < 15 and (ssim is None or ssim > 0.85):
            return ComparisonStatus.GOOD
        if damage_score < 35:
            return ComparisonStatus.WARNING
        return ComparisonStatus.DAMAGED

    @staticmethod
    def _merge_artifact_status(current: str, new_status: str) -> str:
        priority = {"good": 0, "need_check": 1, "maintenance": 1, "warning": 2, "damaged": 3}
        cur_p = priority.get(current, 0)
        new_p = priority.get(new_status, 0)
        return new_status if new_p > cur_p else current

    def _analyze_against_reference(
        self,
        *,
        current_path: Path,
        reference_path: Path | None,
        artifact_id: int,
        ts_ms: int,
    ) -> dict[str, Any]:
        if reference_path is None or not reference_path.exists():
            return {
                "damage_score": 0.0,
                "ssim": None,
                "heatmap_path": None,
                "auto_description": "No reference image; capture saved as baseline.",
                "detections_json": None,
            }

        try:
            import cv2
        except Exception:
            return {
                "damage_score": 0.0,
                "ssim": None,
                "heatmap_path": None,
                "auto_description": "OpenCV not available; analysis skipped.",
                "detections_json": None,
            }

        current = cv2.imread(str(current_path))
        reference = cv2.imread(str(reference_path))
        if current is None or reference is None:
            return {
                "damage_score": 0.0,
                "ssim": None,
                "heatmap_path": None,
                "auto_description": "Could not decode one of the images.",
                "detections_json": None,
            }

        h, w = reference.shape[:2]
        if current.shape[:2] != (h, w):
            current = cv2.resize(current, (w, h))

        gray_cur = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
        gray_ref = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(gray_ref, gray_cur)
        diff_blur = cv2.GaussianBlur(diff, (5, 5), 0)
        _, mask = cv2.threshold(diff_blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)

        damage_pct = float(cv2.countNonZero(mask)) / float(h * w) * 100.0

        heatmap = cv2.applyColorMap(diff_blur, cv2.COLORMAP_JET)
        overlay = cv2.addWeighted(current, 0.6, heatmap, 0.4, 0)
        heatmap_path = current_path.parent / f"heatmap_{ts_ms}.jpg"
        cv2.imwrite(str(heatmap_path), overlay)

        ssim_value: float | None = None
        try:
            from skimage.metrics import structural_similarity
            ssim_value = float(structural_similarity(gray_ref, gray_cur, win_size=7))
        except Exception:
            ssim_value = None

        return {
            "damage_score": damage_pct,
            "ssim": ssim_value,
            "heatmap_path": str(heatmap_path),
            "auto_description": (
                f"Auto: damage area {damage_pct:.1f}%"
                + (f", SSIM {ssim_value:.3f}" if ssim_value is not None else "")
            ),
            "detections_json": None,
        }

    def _publish_alignment_signal(
        self,
        *,
        device_id: str,
        action: str,
        deviation: dict[str, Any],
        artifact_id: str,
        reason: str | None = None,
        iteration: int | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "action": action,
            "task_id": self._command_service.build_task_id(),
            "device_id": device_id,
            "artifact_id": artifact_id,
            "deviation": deviation,
        }
        if reason is not None:
            payload["reason"] = reason
        if iteration is not None:
            payload["iteration"] = iteration

        self._mqtt_bridge.publish_command(device_id, payload)
