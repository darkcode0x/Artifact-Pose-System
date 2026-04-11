from __future__ import annotations

from app.core.config import Settings
from app.services.command_service import CommandService
from app.services.device_registry import DeviceRegistry
from app.services.inspection_service import InspectionService
from app.services.model_service import ModelService
from app.services.mqtt_bridge import MqttBridge
from app.services.pose_service import PoseService


class AppContainer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.device_registry = DeviceRegistry(settings.data_dir / "device_registry.json")
        self.command_service = CommandService(ack_history_limit=settings.ack_history_limit)
        self.mqtt_bridge = MqttBridge(settings, self.command_service)
        self.model_service = ModelService(settings)
        self.pose_service = PoseService(settings)
        self.inspection_service = InspectionService(
            settings=settings,
            pose_service=self.pose_service,
            model_service=self.model_service,
            command_service=self.command_service,
            mqtt_bridge=self.mqtt_bridge,
        )

    def startup(self) -> None:
        self.mqtt_bridge.start()

    def shutdown(self) -> None:
        self.mqtt_bridge.stop()
