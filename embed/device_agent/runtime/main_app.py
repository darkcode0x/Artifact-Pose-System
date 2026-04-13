"""Python Application Layer cho he thong AIoT giam sat co vat."""

from __future__ import annotations

import json
import hashlib
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Dict

from api_client import APIClient, APIConfig
from adapters.camera_manager import CameraManager
from adapters.hardware_controller import HardwareController

# Note: Load env từ file .env nếu có.

def _load_dotenv_file(dotenv_path: Path) -> None:
    """Nap bien moi truong tu file .env neu ton tai."""
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        # Khong ghi de bien da co san tu he thong.
        if key and key not in os.environ:
            os.environ[key] = value


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_first_existing_file(paths: list[Path]) -> str:
    for path in paths:
        try:
            if path.exists():
                content = path.read_text(encoding="utf-8", errors="ignore").strip()
                if content:
                    return content
        except Exception:
            continue
    return ""


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_load_dotenv_file(_PROJECT_ROOT / ".env")
_DEFAULT_IMAGE_DIR = _PROJECT_ROOT / "data" / "pictures"


class ExpiringTaskIdStore:
    """Luu task_id theo TTL de tranh phinh bo nho/idempotency store."""

    def __init__(self, ttl_sec: int, max_entries: int) -> None:
        self.ttl_sec = max(1, ttl_sec)
        self.max_entries = max(100, max_entries)
        self._by_id: Dict[str, float] = {}
        self._expiry_queue: deque[tuple[float, str]] = deque()

    def contains(self, task_id: str, now: float | None = None) -> bool:
        ts = now if now is not None else time.time()
        self._evict_expired(ts)
        return task_id in self._by_id

    def add(self, task_id: str, now: float | None = None) -> None:
        if not task_id:
            return

        ts = now if now is not None else time.time()
        self._evict_expired(ts)

        expire_at = ts + self.ttl_sec
        self._by_id[task_id] = expire_at
        self._expiry_queue.append((expire_at, task_id))
        self._evict_overflow()

    def _evict_expired(self, now: float) -> None:
        while self._expiry_queue and self._expiry_queue[0][0] <= now:
            expire_at, task_id = self._expiry_queue.popleft()
            current_expire = self._by_id.get(task_id)
            if current_expire == expire_at:
                del self._by_id[task_id]

    def _evict_overflow(self) -> None:
        while len(self._by_id) > self.max_entries and self._expiry_queue:
            expire_at, task_id = self._expiry_queue.popleft()
            current_expire = self._by_id.get(task_id)
            if current_expire == expire_at:
                del self._by_id[task_id]

@dataclass
class AppConfig:
    """Cau hinh tong the cho ung dung."""

    # Neu USE_SERVER_DEVICE_ID=true, gia tri nay duoc xem la preferred id (co the bo trong).
    device_id: str = field(default_factory=lambda: _env_str("DEVICE_ID", ""))
    use_server_device_id: bool = field(
        default_factory=lambda: _env_bool("USE_SERVER_DEVICE_ID", True)
    )
    server_base_url: str = field(
        default_factory=lambda: _env_str("SERVER_BASE_URL", "http://127.0.0.1:8000")
    )
    image_dir: Path = field(
        default_factory=lambda: Path(
            _env_str("IMAGE_DIR", str(_DEFAULT_IMAGE_DIR))
        )
    )
    default_artifact_id: str = field(
        default_factory=lambda: _env_str("DEFAULT_ARTIFACT_ID", "artifact_demo_001")
    )

    mqtt_host: str = field(default_factory=lambda: _env_str("MQTT_HOST", "127.0.0.1"))
    mqtt_port: int = field(default_factory=lambda: _env_int("MQTT_PORT", 1883))
    mqtt_keepalive_sec: int = field(
        default_factory=lambda: _env_int("MQTT_KEEPALIVE_SEC", 60)
    )
    mqtt_username: str = field(default_factory=lambda: _env_str("MQTT_USERNAME", ""))
    mqtt_password: str = field(default_factory=lambda: _env_str("MQTT_PASSWORD", ""))
    mqtt_qos: int = field(default_factory=lambda: _env_int("MQTT_QOS", 1))
    mqtt_cmd_topic_template: str = field(
        default_factory=lambda: _env_str("MQTT_CMD_TOPIC_TEMPLATE", "cmd/{device_id}")
    )
    mqtt_ack_topic_template: str = field(
        default_factory=lambda: _env_str("MQTT_ACK_TOPIC_TEMPLATE", "ack/{device_id}")
    )
    mqtt_status_topic_template: str = field(
        default_factory=lambda: _env_str("MQTT_STATUS_TOPIC_TEMPLATE", "status/{device_id}")
    )
    mqtt_reconnect_initial_delay_sec: float = field(
        default_factory=lambda: _env_float("MQTT_RECONNECT_INITIAL_DELAY_SEC", 2.0)
    )
    mqtt_reconnect_max_delay_sec: float = field(
        default_factory=lambda: _env_float("MQTT_RECONNECT_MAX_DELAY_SEC", 30.0)
    )
    task_id_ttl_sec: int = field(default_factory=lambda: _env_int("TASK_ID_TTL_SEC", 180)) #ttl = 3 phut de tranh nhan lenh trung lap
    task_id_cache_max_entries: int = field(
        default_factory=lambda: _env_int("TASK_ID_CACHE_MAX_ENTRIES", 50000)
    )

    # Camera defaults (co the override tu lenh server khi action="capture").
    autofocus_mode: str = field(default_factory=lambda: _env_str("AUTOFOCUS_MODE", "manual"))
    lens_position: float = field(default_factory=lambda: _env_float("LENS_POSITION", 2.5))
    awbgains_r: float = field(default_factory=lambda: _env_float("AWBGAINS_R", 1.2))
    awbgains_b: float = field(default_factory=lambda: _env_float("AWBGAINS_B", 1.5))
    gain: float = field(default_factory=lambda: _env_float("GAIN", 1.0))
    shutter: int = field(default_factory=lambda: _env_int("SHUTTER", 20000))
    pre_set_controls_delay_sec: float = field(
        default_factory=lambda: _env_float("PRE_SET_CONTROLS_DELAY_SEC", 1.5)
    )
    pre_capture_request_delay_sec: float = field(
        default_factory=lambda: _env_float("PRE_CAPTURE_REQUEST_DELAY_SEC", 2.0)
    )
    capture_autofocus_probe_sec: float = field(
        default_factory=lambda: _env_float("CAPTURE_AUTOFOCUS_PROBE_SEC", 0.25)
    )

    # Slider speed profile: 85% chay nhanh, 15% cuoi chay cham de tinh chinh.
    slider_fast_ratio: float = field(
        default_factory=lambda: _env_float("SLIDER_FAST_RATIO", 0.85)
    )
    slider_fast_pulse_delay_sec: float = field(
        default_factory=lambda: _env_float("SLIDER_FAST_PULSE_DELAY_SEC", 0.00035)
    )
    slider_slow_pulse_delay_sec: float = field(
        default_factory=lambda: _env_float("SLIDER_SLOW_PULSE_DELAY_SEC", 0.0008)
    )
    auto_capture_after_move: bool = field(
        default_factory=lambda: _env_bool("AUTO_CAPTURE_AFTER_MOVE", True)
    )


class MainApp:
    """Thin-client tren Raspberry Pi: nhan lenh server va thuc thi."""

    def __init__(
        self,
        config: AppConfig,
    ) -> None:
        self.config = config
        self._machine_hash = self._compute_machine_hash()
        self.api_client = APIClient(
            APIConfig(
                base_url=config.server_base_url,
                device_id=config.device_id or "unassigned",
            )
        )
        self._resolve_device_id()

        self.hardware = HardwareController()
        self.camera = CameraManager(output_dir=config.image_dir)
        self._processed_task_ids = ExpiringTaskIdStore(
            ttl_sec=self.config.task_id_ttl_sec,
            max_entries=self.config.task_id_cache_max_entries,
        )
        self._command_lock = Lock()

        try:
            import paho.mqtt.client as mqtt_client
        except Exception as exc:
            raise RuntimeError(
                "Thieu thu vien paho-mqtt. Cai dat bang: pip install paho-mqtt"
            ) from exc

        self._mqtt_module = mqtt_client
        self._mqtt_client = self._build_mqtt_client()

    def _build_mqtt_client(self) -> Any:
        client = self._mqtt_module.Client(client_id=f"pi-node-{self.config.device_id}")
        if self.config.mqtt_username:
            client.username_pw_set(
                username=self.config.mqtt_username,
                password=self.config.mqtt_password or None,
            )

        client.on_connect = self._on_mqtt_connect
        client.on_message = self._on_mqtt_message
        client.on_disconnect = self._on_mqtt_disconnect

        client.will_set(
            self._status_topic,
            payload=json.dumps(
                {
                    "device_id": self.config.device_id,
                    "status": "offline",
                    "ts_ms": int(time.time() * 1000),
                }
            ),
            qos=self.config.mqtt_qos,
            retain=True,
        )
        return client

    def _resolve_device_id(self) -> None:
        """Dang ky/thiet lap device_id duy nhat voi server truoc khi vao MQTT loop."""
        if not self.config.use_server_device_id:
            if not self.config.device_id:
                # Fallback an toan neu tat server registration nhung khong cau hinh id.
                self.config.device_id = self._compute_machine_hash()
            self.api_client.config.device_id = self.config.device_id
            return

        preferred_id = self.config.device_id.strip() or None

        server_device_id = self.api_client.get_device_id(
            machine_hash=self._machine_hash,
            preferred_device_id=preferred_id,
        )

        if server_device_id:
            self.config.device_id = server_device_id
            print(f"[APP] Nhan device_id tu server: {self.config.device_id}")
        else:
            # Fallback: dung chinh machine hash lam device_id duy nhat.
            self.config.device_id = self._machine_hash
            print(f"[APP] Khong lay duoc id tu server, fallback: {self.config.device_id}")

        self.api_client.config.device_id = self.config.device_id

    def _refresh_device_id_from_server(self) -> bool:
        """Thu lay lai device_id tu server trong qua trinh reconnect."""
        if not self.config.use_server_device_id:
            return False

        preferred_id = self.config.device_id.strip() or None
        server_device_id = self.api_client.get_device_id(
            machine_hash=self._machine_hash,
            preferred_device_id=preferred_id,
        )
        if not server_device_id:
            return False

        if server_device_id == self.config.device_id:
            return False

        old_device_id = self.config.device_id
        self.config.device_id = server_device_id
        self.api_client.config.device_id = server_device_id
        self._mqtt_client = self._build_mqtt_client()
        print(
            f"[APP] Cap nhat device_id tu server: {old_device_id} -> {self.config.device_id}"
        )
        return True

    @staticmethod
    def _compute_machine_hash() -> str:
        """Tao machine fingerprint hash tu nhieu thong so may de giam trung lap."""
        mac_int = uuid.getnode()
        mac_hex = f"{mac_int:012x}"

        # Thu doc machine-id/CPU serial tren Linux.
        machine_id = _read_first_existing_file(
            [
                Path("/etc/machine-id"),
                Path("/var/lib/dbus/machine-id"),
            ]
        )
        cpu_serial = _read_first_existing_file([Path("/proc/cpuinfo")])
        serial_line = ""
        if cpu_serial:
            for line in cpu_serial.splitlines():
                if line.lower().startswith("serial") and ":" in line:
                    serial_line = line.split(":", 1)[1].strip()
                    break

        hostname = _env_str("HOSTNAME", _env_str("COMPUTERNAME", "unknown-host"))
        fingerprint = "|".join(
            [
                f"mac={mac_hex}",
                f"machine_id={machine_id or 'na'}",
                f"cpu_serial={serial_line or 'na'}",
                f"host={hostname}",
            ]
        )

        digest = hashlib.md5(fingerprint.encode("utf-8")).hexdigest()
        return f"md5-{digest}"

    @property
    def _cmd_topic(self) -> str:
        return self.config.mqtt_cmd_topic_template.format(device_id=self.config.device_id)

    @property
    def _ack_topic(self) -> str:
        return self.config.mqtt_ack_topic_template.format(device_id=self.config.device_id)

    @property
    def _status_topic(self) -> str:
        return self.config.mqtt_status_topic_template.format(device_id=self.config.device_id)

    def _on_mqtt_connect(self, client: Any, userdata: Any, flags: Any, rc: int) -> None:
        if rc != 0:
            print(f"[MQTT] Ket noi that bai, rc={rc}")
            return

        client.subscribe(self._cmd_topic, qos=self.config.mqtt_qos)
        print(f"[MQTT] Da subscribe topic lenh: {self._cmd_topic}")
        self._publish_status("online")

    def _on_mqtt_disconnect(self, client: Any, userdata: Any, rc: int) -> None:
        if rc == 0:
            print("[MQTT] Da ngat ket noi chu dong")
            return
        print(f"[MQTT] Mat ket noi broker, rc={rc}, se thu reconnect")

    def _on_mqtt_message(self, client: Any, userdata: Any, msg: Any) -> None:
        try:
            payload = msg.payload.decode("utf-8")
            command = json.loads(payload)
            if not isinstance(command, dict):
                raise ValueError("payload phai la JSON object")
        except Exception as exc:
            print(f"[MQTT] Loi parse command: {exc}")
            return
        print(f"[MQTT] Nhan lenh: {command}")
        result = self.execute_command(command)
        self._publish_ack(command, result)

    def _publish_status(self, status: str) -> None:
        payload = {
            "device_id": self.config.device_id,
            "status": status,
            "ts_ms": int(time.time() * 1000),
        }
        self._mqtt_client.publish(
            self._status_topic,
            payload=json.dumps(payload),
            qos=self.config.mqtt_qos,
            retain=True,
        )

    def _publish_ack(self, command: Dict[str, Any], result: Dict[str, Any]) -> None:
        ack_payload: Dict[str, Any] = {
            "device_id": self.config.device_id,
            "task_id": command.get("task_id"),
            "action": command.get("action", "unknown"),
            "result": result,
            "ts_ms": int(time.time() * 1000),
        }
        self._mqtt_client.publish(
            self._ack_topic,
            payload=json.dumps(ack_payload),
            qos=self.config.mqtt_qos,
            retain=False,
        )

    def execute_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Thuc thi mot lenh nhan duoc va tra ket qua de gui ACK."""
        # Dam bao trong mot thoi diem chi co 1 task_id duoc thuc thi.
        with self._command_lock:
            return self._execute_command_locked(command)

    def _execute_command_locked(self, command: Dict[str, Any]) -> Dict[str, Any]:
        task_id = str(command.get("task_id", "")).strip()
        if task_id and self._processed_task_ids.contains(task_id):
            return {"status": "ignored", "reason": "duplicate_task"}

        action = str(command.get("action", "noop")).lower()

        try:
            if action in {"noop", "none", "idle"}:
                return {"status": "ok", "action": action}

            if action == "reset":
                self.hardware.reset_position()
                self._mark_processed_task(task_id)
                return {"status": "ok", "action": action}

            if action == "pan_tilt":
                self._handle_pan_tilt(command)
                self._mark_processed_task(task_id)
                return {"status": "ok", "action": action}

            if action == "slider_x":
                self._handle_slider_x(command)
                self._mark_processed_task(task_id)
                return {"status": "ok", "action": action}

            if action == "slider_z":
                self._handle_slider_z(command)
                self._mark_processed_task(task_id)
                return {"status": "ok", "action": action}

            if action == "move":
                self._handle_compound_move(command)
                self._mark_processed_task(task_id)
                return {"status": "ok", "action": action}

            if action == "capture":
                self._handle_capture(command)
                self._mark_processed_task(task_id)
                return {"status": "ok", "action": action}

            print(f"[APP] Bo qua action khong ho tro: {action}")
            return {"status": "ignored", "reason": "unsupported_action", "action": action}
        except Exception as exc:
            print(f"[APP] Loi thuc thi lenh {action}: {exc}")
            return {"status": "error", "action": action, "message": str(exc)}

    def _mark_processed_task(self, task_id: str) -> None:
        if task_id:
            self._processed_task_ids.add(task_id)

    def _handle_pan_tilt(self, command: Dict[str, Any]) -> None:
        direction = str(command.get("direction", "")).lower()
        # TODO: angle chi la so nguyen. Nho chuyen ve so nguyen
        angle = int(command.get("angle", 0.0))

        yaw = self.hardware.current_yaw
        pitch = self.hardware.current_pitch

        if direction == "left":
            yaw = -abs(angle)
        elif direction == "right":
            yaw = abs(angle)
        elif direction == "up":
            pitch = abs(angle)
        elif direction == "down":
            pitch = -abs(angle)
        else:
            yaw = int(command.get("yaw_deg", yaw))
            pitch = int(command.get("pitch_deg", pitch))

        self.hardware.set_pan_tilt(yaw, pitch)

    def _handle_slider_x(self, command: Dict[str, Any]) -> None:
        direction = str(command.get("direction", "")).lower()
        step = int(command.get("step", command.get("x_steps", 0)))
        dir_sign = 1 if direction in {"forward", "right", "positive"} else -1
        self._move_slider_x_with_profile(abs(step), dir_sign)

    def _handle_slider_z(self, command: Dict[str, Any]) -> None:
        direction = str(command.get("direction", "")).lower()
        step = int(command.get("step", command.get("z_steps", 0)))
        dir_sign = 1 if direction in {"forward", "up", "positive"} else -1
        self._move_slider_z_with_profile(abs(step), dir_sign)

    def _handle_compound_move(self, command: Dict[str, Any]) -> None:
        # Ho tro schema server gui bo tham so tong hop sau khi tinh pose tren server.
        yaw_target = self._safe_float(command.get("yaw_deg"), self.hardware.current_yaw)
        pitch_target = self._safe_float(command.get("pitch_deg"), self.hardware.current_pitch)
        yaw_target += self._safe_float(command.get("yaw_delta"), 0.0)
        pitch_target += self._safe_float(command.get("pitch_delta"), 0.0)
        x_steps = abs(int(command.get("x_steps", 0)))
        z_steps = abs(int(command.get("z_steps", 0)))
        x_dir = int(command.get("x_dir", 1))
        z_dir = int(command.get("z_dir", 1))

        movement_steps = command.get("movement_steps")
        if isinstance(movement_steps, list):
            for step in movement_steps:
                if not isinstance(step, dict):
                    continue
                axis = str(step.get("axis", "")).lower()
                if axis == "pan":
                    yaw_target += self._safe_float(
                        step.get("delta", step.get("value", 0.0)),
                        0.0,
                    )
                elif axis == "tilt":
                    pitch_target += self._safe_float(
                        step.get("delta", step.get("value", 0.0)),
                        0.0,
                    )
                elif axis in {"slider_x", "x"}:
                    delta = int(step.get("steps", step.get("delta", step.get("value", 0))))
                    x_steps += abs(delta)
                    if delta != 0:
                        x_dir = 1 if delta > 0 else -1
                elif axis in {"slider_z", "z"}:
                    delta = int(step.get("steps", step.get("delta", step.get("value", 0))))
                    z_steps += abs(delta)
                    if delta != 0:
                        z_dir = 1 if delta > 0 else -1

        self._run_parallel_motion(
            yaw_target=yaw_target,
            pitch_target=pitch_target,
            x_steps=x_steps,
            z_steps=z_steps,
            x_dir=1 if x_dir >= 0 else -1,
            z_dir=1 if z_dir >= 0 else -1,
        )

        capture_after_move = command.get("capture_after_move")
        should_capture_after_move = bool(capture_after_move)
        if capture_after_move is None and self.config.auto_capture_after_move:
            workflow = command.get("workflow")
            if isinstance(workflow, dict):
                should_capture_after_move = bool(workflow.get("auto_alignment_loop", False))

        if should_capture_after_move:
            capture_spec = capture_after_move if isinstance(capture_after_move, dict) else {}
            capture_command = self._build_capture_after_move_command(command, capture_spec)
            self._handle_capture(capture_command)

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        if value is None:
            return float(default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _run_parallel_motion(
        self,
        yaw_target: float,
        pitch_target: float,
        x_steps: int,
        z_steps: int,
        x_dir: int,
        z_dir: int,
    ) -> None:
        tasks = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            tasks.append(executor.submit(self.hardware.set_pan_tilt, yaw_target, pitch_target))
            if x_steps > 0:
                tasks.append(executor.submit(self._move_slider_x_with_profile, x_steps, x_dir))
            if z_steps > 0:
                tasks.append(executor.submit(self._move_slider_z_with_profile, z_steps, z_dir))

            for task in tasks:
                task.result()

    def _build_capture_after_move_command(
        self,
        move_command: Dict[str, Any],
        capture_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        artifact_id = str(
            capture_spec.get(
                "artifact_id",
                move_command.get("artifact_id", self.config.default_artifact_id),
            )
        )
        capture_job = str(capture_spec.get("capture_job", "alignment"))
        basename_prefix = str(capture_spec.get("basename_prefix", "align_loop"))
        basename = str(capture_spec.get("basename", f"{basename_prefix}_{artifact_id}_{time.time_ns()}"))

        capture_command: Dict[str, Any] = {
            "action": "capture",
            "artifact_id": artifact_id,
            "capture_job": capture_job,
            "basename": basename,
            "workflow": move_command.get("workflow", {}),
            "server_command": move_command,
        }

        for key in (
            "autofocus_mode",
            "lens_position",
            "awbgains",
            "gain",
            "shutter",
            "pre_set_controls_delay_sec",
            "pre_capture_request_delay_sec",
            "autofocus_probe_sec",
        ):
            if key in capture_spec:
                capture_command[key] = capture_spec[key]

        return capture_command

    def _move_slider_x_with_profile(self, steps: int, direction: int) -> None:
        fast_steps, slow_steps = self._split_step_profile(steps)

        if fast_steps > 0:
            self.hardware.move_slider_x_with_delay(
                fast_steps,
                direction,
                self.config.slider_fast_pulse_delay_sec,
            )
        if slow_steps > 0:
            self.hardware.move_slider_x_with_delay(
                slow_steps,
                direction,
                self.config.slider_slow_pulse_delay_sec,
            )

    def _move_slider_z_with_profile(self, steps: int, direction: int) -> None:
        fast_steps, slow_steps = self._split_step_profile(steps)

        if fast_steps > 0:
            self.hardware.move_slider_z_with_delay(
                fast_steps,
                direction,
                self.config.slider_fast_pulse_delay_sec,
            )
        if slow_steps > 0:
            self.hardware.move_slider_z_with_delay(
                slow_steps,
                direction,
                self.config.slider_slow_pulse_delay_sec,
            )

    def _split_step_profile(self, total_steps: int) -> tuple[int, int]:
        if total_steps <= 0:
            return 0, 0

        fast_ratio = max(0.0, min(1.0, self.config.slider_fast_ratio))
        fast_steps = int(total_steps * fast_ratio)

        # Giup hanh trinh ngan van co pha tinh chinh o cuoi.
        if total_steps > 1:
            fast_steps = min(fast_steps, total_steps - 1)

        slow_steps = total_steps - fast_steps
        return fast_steps, slow_steps

    def _handle_capture(self, command: Dict[str, Any]) -> None:
        artifact_id = str(command.get("artifact_id", self.config.default_artifact_id))
        capture_job = str(command.get("capture_job", "alignment")).strip().lower()
        default_prefix = "golden_sample" if capture_job == "golden_sample" else "align_capture"
        basename = str(command.get("basename", f"{default_prefix}_{artifact_id}_{time.time_ns()}"))

        autofocus_mode = str(command.get("autofocus_mode", self.config.autofocus_mode))
        lens_position = float(command.get("lens_position", self.config.lens_position))
        awbgains = command.get("awbgains", (self.config.awbgains_r, self.config.awbgains_b))
        if not isinstance(awbgains, (list, tuple)) or len(awbgains) != 2:
            awbgains = (self.config.awbgains_r, self.config.awbgains_b)
        gain = float(command.get("gain", self.config.gain))
        shutter = int(command.get("shutter", self.config.shutter))
        pre_set_delay = float(
            command.get(
                "pre_set_controls_delay_sec",
                self.config.pre_set_controls_delay_sec,
            )
        )
        pre_capture_delay = float(
            command.get(
                "pre_capture_request_delay_sec",
                self.config.pre_capture_request_delay_sec,
            )
        )
        autofocus_probe_sec = float(
            command.get(
                "autofocus_probe_sec",
                self.config.capture_autofocus_probe_sec,
            )
        )

        capture_outcome = self.camera.capture_high_quality_with_metadata(
            basename=basename,
            autofocus_mode=autofocus_mode,
            lens_position=lens_position,
            awbgains=awbgains,
            gain=gain,
            shutter=shutter,
            pre_set_controls_delay_sec=pre_set_delay,
            pre_capture_request_delay_sec=pre_capture_delay,
            autofocus_probe_sec=autofocus_probe_sec,
        )
        if capture_outcome is None:
            print("[APP] Capture that bai theo lenh server")
            return

        capture_name_type = "reference_sample" if capture_job == "golden_sample" else "alignment_image"

        # Pi chi dong vai tro uploader trang thai va metadata, viec tinh toan pose/controls se duoc thuc hien tren server.
        metadata: Dict[str, Any] = {
            "yaw_deg": float(self.hardware.current_yaw),
            "pitch_deg": float(self.hardware.current_pitch),
            "x_steps": int(self.hardware.current_x_steps),
            "z_steps": int(self.hardware.current_z_steps),
            "capture_job": capture_job,
            "capture_name_type": capture_name_type,
            "camera_static_params": {
                "autofocus_mode": autofocus_mode,
                "lens_position": lens_position,
                "awbgains": [float(awbgains[0]), float(awbgains[1])],
                "gain": gain,
                "shutter": shutter,
                "pre_set_controls_delay_sec": pre_set_delay,
                "pre_capture_request_delay_sec": pre_capture_delay,
                "autofocus_probe_sec": autofocus_probe_sec,
            },
            "camera_runtime_metadata": capture_outcome.metadata,
            "workflow": command.get("workflow", {}),
            "server_command": command,
        }

        uploaded = self.api_client.upload_inspection(
            image_path=capture_outcome.image_path,
            device_id=self.config.device_id,
            artifact_id=artifact_id,
            calibration_data=metadata,
        )
        if not uploaded:
            print("[APP] Upload inspection that bai")

    def run(self) -> None:
        """Main loop: ket noi MQTT va tu dong reconnect khi co su co mang/server."""
        initial_delay = max(1.0, self.config.mqtt_reconnect_initial_delay_sec)
        max_delay = max(initial_delay, self.config.mqtt_reconnect_max_delay_sec)
        reconnect_delay = initial_delay

        try:
            while True:
                self._refresh_device_id_from_server()
                try:
                    self._mqtt_client.connect(
                        host=self.config.mqtt_host,
                        port=self.config.mqtt_port,
                        keepalive=self.config.mqtt_keepalive_sec,
                    )
                    reconnect_delay = initial_delay
                    self._mqtt_client.loop_forever()
                    print("[MQTT] Vong loop ket thuc, chuan bi reconnect")
                except KeyboardInterrupt:
                    raise
                except Exception as exc:
                    print(f"[MQTT] Loi ket noi/loop: {exc}")

                print(f"[MQTT] Thu ket noi lai sau {reconnect_delay:.1f}s")
                time.sleep(reconnect_delay)
                reconnect_delay = min(max_delay, reconnect_delay * 2.0)
        except KeyboardInterrupt:
            print("[APP] Dung chuong trinh")
        finally:
            try:
                self._publish_status("offline")
                self._mqtt_client.disconnect()
            except Exception:
                pass
            self.hardware.cleanup()


if __name__ == "__main__":
    app = MainApp(AppConfig())
    app.run()