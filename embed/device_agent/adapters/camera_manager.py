"""Quan ly camera Pi Camera Module V3 voi che do thong so thu cong."""

from __future__ import annotations

import importlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence


@dataclass
class CaptureOutcome:
    image_path: Path
    metadata: dict[str, Any]


class CameraManager:
    """Dieu khien viec chup anh 12MP voi cau hinh AF/AWB/AEC thu cong."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def capture_high_quality(
        self,
        basename: str,
        autofocus_mode: str = "manual",
        lens_position: float = 2.5,
        awbgains: Sequence[float] = (1.2, 1.5),
        gain: float = 1.0,
        shutter: int = 20000,
        pre_set_controls_delay_sec: float = 1.5,
        pre_capture_request_delay_sec: float = 2.0,
    ) -> Optional[Path]:
        outcome = self.capture_high_quality_with_metadata(
            basename=basename,
            autofocus_mode=autofocus_mode,
            lens_position=lens_position,
            awbgains=awbgains,
            gain=gain,
            shutter=shutter,
            pre_set_controls_delay_sec=pre_set_controls_delay_sec,
            pre_capture_request_delay_sec=pre_capture_request_delay_sec,
        )
        if outcome is None:
            return None
        return outcome.image_path

    def capture_high_quality_with_metadata(
        self,
        basename: str,
        autofocus_mode: str = "manual",
        lens_position: float = 2.5,
        awbgains: Sequence[float] = (1.2, 1.5),
        gain: float = 1.0,
        shutter: int = 20000,
        pre_set_controls_delay_sec: float = 1.5,
        pre_capture_request_delay_sec: float = 2.0,
        autofocus_probe_sec: float = 0.25,
    ) -> Optional[CaptureOutcome]:
        """Chup anh chat luong cao 12MP va tra metadata runtime camera."""
        image_path = self.output_dir / f"{basename}.png"

        try:
            picamera2_module = importlib.import_module("picamera2")
            libcamera_module = importlib.import_module("libcamera")
            Picamera2 = getattr(picamera2_module, "Picamera2")
            controls = getattr(libcamera_module, "controls")
        except Exception as exc:
            print(f"[CAM] Khong the import Picamera2/libcamera: {exc}")
            return None

        picam2 = None
        started = False
        try:
            picam2 = Picamera2()
            config = picam2.create_still_configuration(
                main={"size": picam2.sensor_resolution, "format": "RGB888"},
                raw={"size": picam2.sensor_resolution},
                controls={"AwbEnable": False},
            )
            picam2.configure(config)
            picam2.start()
            started = True

            time.sleep(max(0.0, pre_set_controls_delay_sec))

            runtime_metadata: dict[str, Any] = {}
            af_lens_position = self._probe_autofocus_lens(
                picam2,
                controls,
                autofocus_probe_sec,
            )
            if af_lens_position is not None:
                runtime_metadata["autofocus_lens_position"] = float(af_lens_position)

            af_manual = controls.AfModeEnum.Manual
            if autofocus_mode.lower() != "manual":
                print("[CAM] Canh bao: se van ep AF manual theo yeu cau")

            effective_lens_position = (
                float(af_lens_position) if af_lens_position is not None else float(lens_position)
            )

            picam2.set_controls(
                {
                    "AfMode": af_manual,
                    "LensPosition": effective_lens_position,
                    "AeEnable": False,
                    "AwbEnable": False,
                    "ColourGains": tuple(float(x) for x in awbgains),
                    "AnalogueGain": float(gain),
                    "ExposureTime": int(shutter),
                }
            )

            time.sleep(max(0.0, pre_capture_request_delay_sec))

            request = picam2.capture_request()
            request.save("main", str(image_path))
            try:
                capture_meta = request.get_metadata() or {}
            except Exception:
                capture_meta = {}
            request.release()

            runtime_metadata.update(self._extract_runtime_metadata(capture_meta))
            runtime_metadata["applied_lens_position"] = effective_lens_position
            runtime_metadata["configured_lens_position"] = float(lens_position)
            runtime_metadata["awb_gains"] = [float(awbgains[0]), float(awbgains[1])]
            runtime_metadata["analogue_gain"] = float(gain)
            runtime_metadata["exposure_time"] = int(shutter)

            print(f"[CAM] Da chup anh: {image_path}")
            return CaptureOutcome(image_path=image_path, metadata=runtime_metadata)
        except Exception as exc:
            print(f"[CAM] Loi chup anh: {exc}")
            return None
        finally:
            if picam2 is not None:
                try:
                    if started:
                        picam2.stop()
                except Exception:
                    pass
                try:
                    picam2.close()
                except Exception:
                    pass

    @staticmethod
    def _probe_autofocus_lens(
        picam2: Any,
        controls: Any,
        autofocus_probe_sec: float,
    ) -> float | None:
        try:
            picam2.set_controls({"AfMode": controls.AfModeEnum.Auto})
            try:
                picam2.set_controls({"AfTrigger": controls.AfTriggerEnum.Start})
            except Exception:
                pass
            time.sleep(max(0.0, autofocus_probe_sec))
            af_meta = picam2.capture_metadata() or {}
            lens = af_meta.get("LensPosition")
            if lens is None:
                lens = af_meta.get("LensPositionRaw")
            if lens is None:
                return None
            return float(lens)
        except Exception:
            return None

    @staticmethod
    def _extract_runtime_metadata(raw: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if not isinstance(raw, dict):
            return result

        for key in ("LensPosition", "AnalogueGain", "ExposureTime", "SensorTimestamp"):
            if key in raw:
                result[key.lower()] = raw.get(key)

        if "ColourGains" in raw:
            value = raw.get("ColourGains")
            if isinstance(value, (list, tuple)) and len(value) == 2:
                result["awb_gains_runtime"] = [float(value[0]), float(value[1])]

        return result
