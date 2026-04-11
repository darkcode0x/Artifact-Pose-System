from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from app.api.dependencies import get_container
from app.services.state import AppContainer

router = APIRouter()


@router.get("/")
def root() -> dict[str, str]:
    return {
        "service": "IoT Artifact Server",
        "docs": "/docs",
        "health": "/health",
    }


@router.get("/health")
def health(container: AppContainer = Depends(get_container)) -> dict[str, str]:
    state = container.mqtt_bridge.state()["state"]
    return {
        "status": "ok",
        "mqtt_connected": str(bool(state.get("connected"))).lower(),
    }


@router.get("/mqtt/health")
def mqtt_health(container: AppContainer = Depends(get_container)) -> dict:
    return {
        "ok": True,
        **container.mqtt_bridge.state(),
    }


@router.get("/mqtt/events")
def mqtt_events(
    limit: int = 100,
    container: AppContainer = Depends(get_container),
) -> dict:
    safe_limit = max(1, min(500, int(limit)))
    log_file = container.settings.mqtt_event_log_file
    if not log_file.exists():
        return {
            "ok": True,
            "count": 0,
            "events": [],
        }

    rows: list[dict] = []
    for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(parsed)
        except Exception:
            continue

    events = rows[-safe_limit:]
    return {
        "ok": True,
        "count": len(events),
        "events": events,
    }
