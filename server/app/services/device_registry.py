from __future__ import annotations

import json
import re
from pathlib import Path
from threading import Lock


class DeviceRegistry:
    def __init__(self, registry_file: Path) -> None:
        self._registry_file = registry_file
        self._machine_to_device: dict[str, str] = {}
        self._device_to_machine: dict[str, str] = {}
        self._lock = Lock()
        self._load()

    def _load(self) -> None:
        if not self._registry_file.exists():
            return

        try:
            data = json.loads(self._registry_file.read_text(encoding="utf-8"))
        except Exception:
            return

        machine_to_device = data.get("machine_to_device")
        if not isinstance(machine_to_device, dict):
            return

        for machine_hash, device_id in machine_to_device.items():
            if not isinstance(machine_hash, str) or not isinstance(device_id, str):
                continue
            if not machine_hash.strip() or not device_id.strip():
                continue
            self._machine_to_device[machine_hash] = device_id
            self._device_to_machine[device_id] = machine_hash

    def _save_locked(self) -> None:
        payload = {
            "machine_to_device": self._machine_to_device,
        }
        self._registry_file.parent.mkdir(parents=True, exist_ok=True)
        self._registry_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _normalize_device_id(value: str) -> str:
        lowered = value.lower().strip()
        normalized = re.sub(r"[^a-z0-9\-_]", "-", lowered)
        normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
        return normalized

    def allocate_device_id(self, machine_hash: str, preferred_device_id: str | None = None) -> str:
        machine_key = machine_hash.strip()
        if not machine_key:
            raise ValueError("machine_hash is required")

        with self._lock:
            existing = self._machine_to_device.get(machine_key)
            if existing:
                return existing

            preferred = self._normalize_device_id(preferred_device_id or "")
            if preferred and preferred not in self._device_to_machine:
                assigned = preferred
            else:
                short_hash = machine_key.replace("md5-", "")[:10] or "unknown"
                base = f"dev-{short_hash}"
                assigned = base
                suffix = 1
                while assigned in self._device_to_machine:
                    suffix += 1
                    assigned = f"{base}-{suffix}"

            self._machine_to_device[machine_key] = assigned
            self._device_to_machine[assigned] = machine_key
            self._save_locked()
            return assigned
