"""Quan ly camera Pi Camera Module V3 voi che do thong so thu cong."""

from __future__ import annotations

import importlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

try:
    import numpy as np
except Exception:
    np = None


@dataclass
class CaptureOutcome:
    image_path: Path
    metadata: dict[str, Any]


class CameraManager:
    """Dieu khien viec chup anh 12MP voi cau hinh AF/AWB/AEC thu cong."""

    _DARK_MEAN_THRESHOLD = 20.0
    _FLAT_STD_THRESHOLD = 4.0
    _MIN_DYNAMIC_RANGE = 18.0
    _MAX_BLACK_RATIO = 0.90

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

            capture_meta, capture_quality = self._capture_request_with_quality(
                picam2,
                image_path,
            )
            runtime_metadata["capture_quality_primary"] = capture_quality

            # Neu anh qua toi/gan nhu phang (all-black), thu lai bang auto-exposure.
            if not capture_quality.get("usable", True):
                print("[CAM] Anh qua toi/it texture, thu chup lai voi auto exposure")
                capture_meta, capture_quality = self._capture_with_auto_exposure(
                    picam2,
                    controls,
                    image_path,
                    settle_sec=max(1.2, pre_capture_request_delay_sec),
                )
                runtime_metadata["capture_quality_fallback_auto"] = capture_quality
                runtime_metadata["fallback_auto_exposure_used"] = True

            # Neu van toi sau auto-exposure, boost gain/shutter de tranh black frame.
            if not capture_quality.get("usable", True):
                print("[CAM] Auto exposure chua dat, thu boost gain/shutter")
                capture_meta, capture_quality = self._capture_with_boosted_manual(
                    picam2,
                    controls,
                    image_path,
                    lens_position=effective_lens_position,
                    awbgains=awbgains,
                    base_gain=gain,
                    base_shutter=shutter,
                    settle_sec=max(0.8, pre_capture_request_delay_sec),
                )
                runtime_metadata["capture_quality_fallback_boosted"] = capture_quality
                runtime_metadata["fallback_boosted_used"] = True

            runtime_metadata["capture_quality"] = capture_quality

            runtime_metadata.update(self._extract_runtime_metadata(capture_meta))
            runtime_metadata["applied_lens_position"] = effective_lens_position
            runtime_metadata["configured_lens_position"] = float(lens_position)
            runtime_metadata["awb_gains"] = [float(awbgains[0]), float(awbgains[1])]
            runtime_metadata["analogue_gain"] = float(gain)
            runtime_metadata["exposure_time"] = int(shutter)

            mean_luma = runtime_metadata.get("capture_quality", {}).get("mean_luma")
            print(f"[CAM] Da chup anh: {image_path} (mean_luma={mean_luma})")
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

    def _capture_request_with_quality(
        self,
        picam2: Any,
        image_path: Path,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        request = picam2.capture_request()
        frame = None

        try:
            try:
                frame = request.make_array("main")
            except Exception:
                frame = None

            request.save("main", str(image_path))
            try:
                capture_meta = request.get_metadata() or {}
            except Exception:
                capture_meta = {}
        finally:
            request.release()

        quality = self._analyze_image_quality(frame)
        return capture_meta, quality

    def _capture_with_auto_exposure(
        self,
        picam2: Any,
        controls: Any,
        image_path: Path,
        settle_sec: float,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            picam2.set_controls(
                {
                    "AeEnable": True,
                    "AwbEnable": True,
                    "AfMode": controls.AfModeEnum.Auto,
                }
            )
            try:
                picam2.set_controls({"AfTrigger": controls.AfTriggerEnum.Start})
            except Exception:
                pass
            time.sleep(max(0.0, settle_sec))
            meta, quality = self._capture_request_with_quality(picam2, image_path)
            quality["capture_mode"] = "fallback_auto_exposure"
            return meta, quality
        except Exception as exc:
            return {}, {
                "usable": False,
                "reason": f"fallback_auto_exposure_failed:{exc}",
                "capture_mode": "fallback_auto_exposure",
            }

    def _capture_with_boosted_manual(
        self,
        picam2: Any,
        controls: Any,
        image_path: Path,
        lens_position: float,
        awbgains: Sequence[float],
        base_gain: float,
        base_shutter: int,
        settle_sec: float,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        boosted_gain = min(16.0, max(6.0, float(base_gain) * 4.0))
        boosted_shutter = min(300000, max(80000, int(base_shutter) * 4))

        try:
            picam2.set_controls(
                {
                    "AfMode": controls.AfModeEnum.Manual,
                    "LensPosition": float(lens_position),
                    "AeEnable": False,
                    "AwbEnable": False,
                    "ColourGains": tuple(float(x) for x in awbgains),
                    "AnalogueGain": float(boosted_gain),
                    "ExposureTime": int(boosted_shutter),
                }
            )
            time.sleep(max(0.0, settle_sec))
            meta, quality = self._capture_request_with_quality(picam2, image_path)
            quality["capture_mode"] = "fallback_boosted_manual"
            quality["boosted_gain"] = float(boosted_gain)
            quality["boosted_shutter"] = int(boosted_shutter)
            return meta, quality
        except Exception as exc:
            return {}, {
                "usable": False,
                "reason": f"fallback_boosted_manual_failed:{exc}",
                "capture_mode": "fallback_boosted_manual",
                "boosted_gain": float(boosted_gain),
                "boosted_shutter": int(boosted_shutter),
            }

    @classmethod
    def _analyze_image_quality(cls, frame: Any) -> dict[str, Any]:
        if frame is None or np is None:
            return {
                "usable": True,
                "reason": "quality_check_unavailable",
            }

        try:
            arr = np.asarray(frame)
        except Exception:
            return {
                "usable": True,
                "reason": "quality_check_unavailable",
            }

        if arr.size == 0:
            return {
                "usable": False,
                "reason": "empty_frame",
            }

        if arr.ndim == 3:
            gray = arr.astype(np.float32).mean(axis=2)
        else:
            gray = arr.astype(np.float32)

        mean_luma = float(gray.mean())
        std_luma = float(gray.std())
        p01 = float(np.percentile(gray, 1))
        p99 = float(np.percentile(gray, 99))
        dynamic_range = p99 - p01
        black_ratio = float((gray <= 8.0).mean())

        too_dark = mean_luma < cls._DARK_MEAN_THRESHOLD and black_ratio > cls._MAX_BLACK_RATIO
        too_flat = std_luma < cls._FLAT_STD_THRESHOLD and dynamic_range < cls._MIN_DYNAMIC_RANGE
        usable = not (too_dark or too_flat)

        reason = "ok"
        if not usable:
            if too_dark and too_flat:
                reason = "dark_and_flat"
            elif too_dark:
                reason = "too_dark"
            else:
                reason = "too_flat"

        return {
            "usable": bool(usable),
            "reason": reason,
            "mean_luma": round(mean_luma, 3),
            "std_luma": round(std_luma, 3),
            "dynamic_range": round(dynamic_range, 3),
            "black_ratio": round(black_ratio, 5),
        }

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
