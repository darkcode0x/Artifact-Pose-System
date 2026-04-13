from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _load_dotenv_file(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    if raw.strip() == "":
        return default
    return raw


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float | None = None) -> float | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _csv(value: str) -> list[str]:
    if not value.strip():
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


SERVER_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = SERVER_ROOT.parent
_load_dotenv_file(SERVER_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    app_host: str
    app_port: int
    cors_allow_origins: list[str]

    data_dir: Path
    model_dir: Path
    run_pose_on_upload: bool
    run_ai_on_upload: bool
    auto_dispatch_pose_command: bool

    mqtt_host: str
    mqtt_port: int
    mqtt_keepalive_sec: int
    mqtt_username: str
    mqtt_password: str
    mqtt_qos: int
    mqtt_cmd_topic_template: str
    mqtt_ack_topic_template: str
    mqtt_status_topic_template: str

    artifact_pose_root: Path
    artifact_camera_params_dir: Path
    artifact_camera_params: Path
    artifact_lens_position: float | None
    artifact_golden_pose: Path

    ack_history_limit: int

    max_alignment_iterations: int
    alignment_timeout_sec: int

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def inspections_log_file(self) -> Path:
        return self.logs_dir / "inspections_log.jsonl"

    @property
    def mqtt_event_log_file(self) -> Path:
        return self.logs_dir / "mqtt_events.jsonl"


def ensure_directories(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.model_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    artifact_pose_root_raw = _env_str(
        "ARTIFACT_POSE_ROOT",
        str(SERVER_ROOT / "app" / "modules" / "artifact_pose"),
    )
    artifact_pose_root = Path(artifact_pose_root_raw)

    camera_params_default = SERVER_ROOT / "data" / "camera_params.yaml"
    camera_params_dir_default = SERVER_ROOT / "data" / "camera_params"
    golden_pose_default = SERVER_ROOT / "data" / "golden_pose.yaml"

    artifact_camera_params_dir = Path(
        _env_str("ARTIFACT_CAMERA_PARAMS_DIR", str(camera_params_dir_default))
    )
    artifact_lens_position = _env_float("ARTIFACT_LENS_POSITION", None)

    if artifact_lens_position is not None:
        artifact_lens_position = round(round(artifact_lens_position * 10.0) / 10.0, 1)

    explicit_camera_params = os.getenv("ARTIFACT_CAMERA_PARAMS")
    if explicit_camera_params is not None and explicit_camera_params.strip() != "":
        artifact_camera_params = Path(explicit_camera_params)
    elif artifact_lens_position is not None:
        artifact_camera_params = (
            artifact_camera_params_dir / f"camera_params_lens_{artifact_lens_position:.1f}.yaml"
        )
    else:
        artifact_camera_params = camera_params_default

    origins_raw = _env_str("CORS_ALLOW_ORIGINS", "*")
    origins = _csv(origins_raw)
    if not origins:
        origins = ["*"]

    data_dir_raw = _env_str("DATA_DIR", str(SERVER_ROOT / "data"))
    model_dir_raw = _env_str("MODEL_DIR", str(WORKSPACE_ROOT / "model"))

    return Settings(
        app_name=_env_str("APP_NAME", "IoT Artifact Server"),
        app_version=_env_str("APP_VERSION", "1.0.0"),
        app_host=_env_str("APP_HOST", "0.0.0.0"),
        app_port=_env_int("APP_PORT", 8000),
        cors_allow_origins=origins,
        data_dir=Path(data_dir_raw),
        model_dir=Path(model_dir_raw),
        run_pose_on_upload=_env_bool("RUN_POSE_ON_UPLOAD", True),
        run_ai_on_upload=_env_bool("RUN_AI_ON_UPLOAD", False),
        auto_dispatch_pose_command=_env_bool("AUTO_DISPATCH_POSE_COMMAND", True),
        mqtt_host=_env_str("MQTT_HOST", "127.0.0.1"),
        mqtt_port=_env_int("MQTT_PORT", 1883),
        mqtt_keepalive_sec=_env_int("MQTT_KEEPALIVE_SEC", 60),
        mqtt_username=_env_str("MQTT_USERNAME", ""),
        mqtt_password=_env_str("MQTT_PASSWORD", ""),
        mqtt_qos=max(0, min(2, _env_int("MQTT_QOS", 1))),
        mqtt_cmd_topic_template=_env_str("MQTT_CMD_TOPIC_TEMPLATE", "cmd/{device_id}"),
        mqtt_ack_topic_template=_env_str("MQTT_ACK_TOPIC_TEMPLATE", "ack/{device_id}"),
        mqtt_status_topic_template=_env_str(
            "MQTT_STATUS_TOPIC_TEMPLATE",
            "status/{device_id}",
        ),
        artifact_pose_root=artifact_pose_root,
        artifact_camera_params_dir=artifact_camera_params_dir,
        artifact_camera_params=artifact_camera_params,
        artifact_lens_position=artifact_lens_position,
        artifact_golden_pose=Path(_env_str("ARTIFACT_GOLDEN_POSE", str(golden_pose_default))),
        ack_history_limit=max(1, _env_int("ACK_HISTORY_LIMIT", 200)),
        max_alignment_iterations=max(1, _env_int("MAX_ALIGNMENT_ITERATIONS", 20)),
        alignment_timeout_sec=max(10, _env_int("ALIGNMENT_TIMEOUT_SEC", 300)),
    )
