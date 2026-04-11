from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.core.config import Settings
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

        if pose_result.get("deviation") is None:
            return {
                "ok": False,
                "sent": False,
                "reason": "missing_deviation",
            }

        deviation = pose_result.get("deviation") or {}
        if bool(deviation.get("within_tolerance", False)):
            return {
                "ok": True,
                "sent": False,
                "reason": "within_tolerance",
            }

        motor_command = pose_result.get("motor_command") or deviation.get("motor_command") or {}
        if not isinstance(motor_command, dict):
            return {
                "ok": False,
                "sent": False,
                "reason": "invalid_motor_command",
            }

        move_x = float(motor_command.get("move_x", 0.0) or 0.0)
        move_z = float(motor_command.get("move_z", 0.0) or 0.0)
        rotate_pan = float(motor_command.get("rotate_pan", 0.0) or 0.0)
        rotate_tilt = float(motor_command.get("rotate_tilt", 0.0) or 0.0)

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
