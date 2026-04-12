#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any


class SmokeError(RuntimeError):
    pass


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _http_json(method: str, url: str, payload: dict[str, Any] | None, timeout_sec: float) -> dict[str, Any]:
    body: bytes | None = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, method=method, data=body, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SmokeError(f"HTTP {exc.code} at {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SmokeError(f"Network error at {url}: {exc}") from exc

    if not raw.strip():
        return {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SmokeError(f"Invalid JSON response at {url}: {raw[:300]}") from exc

    if not isinstance(parsed, dict):
        raise SmokeError(f"Expected JSON object at {url}, got {type(parsed).__name__}")

    return parsed


def _extract_device_id_from_topic(topic: str) -> str | None:
    parts = [item for item in topic.strip("/").split("/") if item]
    if len(parts) < 2:
        return None
    return parts[-1]


def _discover_online_device_id(base_url: str, timeout_sec: float, poll_interval_sec: float) -> str:
    deadline = time.time() + max(1.0, timeout_sec)

    while time.time() < deadline:
        events = _http_json(
            method="GET",
            url=_url(base_url, "/mqtt/events?limit=100"),
            payload=None,
            timeout_sec=8,
        )

        rows = events.get("events")
        if isinstance(rows, list):
            online_candidates: list[tuple[int, str]] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if row.get("event_type") != "status":
                    continue

                payload = row.get("payload")
                if not isinstance(payload, dict):
                    continue
                status_value = str(payload.get("status", "")).strip().lower()
                if status_value != "online":
                    continue

                topic = str(row.get("topic", "")).strip()
                device_id = _extract_device_id_from_topic(topic)
                if not device_id:
                    continue

                ts_raw = row.get("timestamp_ms")
                try:
                    ts = int(ts_raw)
                except Exception:
                    ts = 0

                online_candidates.append((ts, device_id))

            if online_candidates:
                online_candidates.sort(key=lambda x: x[0], reverse=True)
                return online_candidates[0][1]

        time.sleep(max(0.2, poll_interval_sec))

    raise SmokeError(
        "Could not discover an online device from /mqtt/events. "
        "Provide --device-id or run with --ssh-host to auto-start the Pi agent."
    )


def _find_ack_for_task(acks_payload: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    rows = acks_payload.get("acks")
    if not isinstance(rows, list):
        return None

    for item in reversed(rows):
        if not isinstance(item, dict):
            continue
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        if str(payload.get("task_id")) == task_id:
            return payload

    return None


def _wait_for_ack(
    base_url: str,
    device_id: str,
    task_id: str,
    timeout_sec: float,
    poll_interval_sec: float,
    require_ok: bool,
) -> dict[str, Any]:
    deadline = time.time() + max(1.0, timeout_sec)
    ack_url = _url(base_url, f"/devices/{device_id}/acks?limit=200")

    while time.time() < deadline:
        acks_payload = _http_json("GET", ack_url, None, 8)
        found = _find_ack_for_task(acks_payload, task_id)
        if found is not None:
            if require_ok:
                result = found.get("result")
                if not isinstance(result, dict) or str(result.get("status", "")).lower() != "ok":
                    raise SmokeError(
                        "ACK received but status is not ok: "
                        f"{json.dumps(found, ensure_ascii=False)}"
                    )
            return found

        time.sleep(max(0.2, poll_interval_sec))

    raise SmokeError(f"Timed out waiting ACK for task_id={task_id}")


def _start_remote_agent(args: argparse.Namespace) -> subprocess.Popen[str] | None:
    if args.no_remote_agent:
        return None

    if not args.ssh_host.strip():
        raise SmokeError("--ssh-host is required unless --no-remote-agent is used")

    remote_workdir = args.ssh_workdir.strip()
    if remote_workdir.startswith("~/"):
        remote_workdir = "$HOME/" + remote_workdir[2:]

    escaped_workdir = remote_workdir.replace("\\", "\\\\").replace('"', '\\"')

    remote_cmd = (
        f"cd \"{escaped_workdir}\" && "
        f"PYTHONPATH=. PYTHONUNBUFFERED=1 timeout -s INT {int(args.agent_runtime_sec)} "
        "python3 -m runtime.main_app"
    )
    target = f"{args.ssh_user}@{args.ssh_host}"

    ssh_base = ["ssh", "-o", "StrictHostKeyChecking=no", target, remote_cmd]

    if args.ssh_password:
        if shutil.which("sshpass") is None:
            raise SmokeError("sshpass is required when --ssh-password is provided")
        cmd = ["sshpass", "-p", args.ssh_password, *ssh_base]
    else:
        cmd = ssh_base

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _stop_remote_agent(proc: subprocess.Popen[str] | None) -> list[str]:
    if proc is None:
        return []

    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)

    if proc.stdout is None:
        return []

    try:
        content = proc.stdout.read()
    except Exception:
        return []

    lines = [line for line in content.splitlines() if line.strip()]
    if len(lines) > 40:
        lines = lines[-40:]
    return lines


def _default_move_payload() -> dict[str, Any]:
    return {
        "action": "move",
        "yaw_delta": 1.0,
        "pitch_delta": -0.5,
        "x_steps": 2,
        "z_steps": 1,
        "x_dir": 1,
        "z_dir": 1,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test API + MQTT + ACK in one command",
    )

    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--http-timeout-sec", type=float, default=8.0)

    parser.add_argument("--device-id", default="")
    parser.add_argument("--ack-timeout-sec", type=float, default=20.0)
    parser.add_argument("--poll-interval-sec", type=float, default=1.0)
    parser.add_argument("--discover-timeout-sec", type=float, default=20.0)

    parser.add_argument("--no-remote-agent", action="store_true")
    parser.add_argument("--ssh-host", default="100.83.253.100")
    parser.add_argument("--ssh-user", default="pi")
    parser.add_argument("--ssh-password", default=os.getenv("SMOKE_PI_PASSWORD", ""))
    parser.add_argument(
        "--ssh-workdir",
        default="~/Artifact-Pose-System/embed/device_agent",
    )
    parser.add_argument("--agent-warmup-sec", type=float, default=5.0)
    parser.add_argument("--agent-runtime-sec", type=float, default=90.0)

    parser.add_argument(
        "--allow-ack-non-ok",
        action="store_true",
        help="Do not fail if ACK is received with result.status != ok",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")

    remote_proc: subprocess.Popen[str] | None = None

    try:
        print("[1/7] Checking API health...")
        health = _http_json("GET", _url(base_url, "/health"), None, args.http_timeout_sec)
        if str(health.get("status", "")).lower() != "ok":
            raise SmokeError(f"/health is not ok: {health}")

        print("[2/7] Checking MQTT bridge health...")
        mqtt_health = _http_json("GET", _url(base_url, "/mqtt/health"), None, args.http_timeout_sec)
        state = mqtt_health.get("state")
        if not isinstance(state, dict) or not bool(state.get("connected")):
            raise SmokeError(f"MQTT bridge is not connected: {mqtt_health}")

        if not args.no_remote_agent:
            print("[3/7] Starting Raspberry agent over SSH...")
            remote_proc = _start_remote_agent(args)
            time.sleep(max(1.0, args.agent_warmup_sec))
            if remote_proc is not None and remote_proc.poll() is not None:
                raise SmokeError(
                    f"Remote agent exited early with code {remote_proc.returncode}. "
                    "Check SSH credentials and remote runtime dependencies."
                )
        else:
            print("[3/7] Skipping remote agent start (--no-remote-agent).")

        print("[4/7] Resolving target device id...")
        if args.device_id.strip():
            device_id = args.device_id.strip()
        else:
            device_id = _discover_online_device_id(
                base_url=base_url,
                timeout_sec=args.discover_timeout_sec,
                poll_interval_sec=args.poll_interval_sec,
            )
        print(f"      Device: {device_id}")

        print("[5/7] Sending move command via /devices/{device_id}/queue_move...")
        queue_resp = _http_json(
            "POST",
            _url(base_url, f"/devices/{device_id}/queue_move"),
            _default_move_payload(),
            args.http_timeout_sec,
        )

        if not bool(queue_resp.get("published")):
            raise SmokeError(f"Command was not published via MQTT: {queue_resp}")

        task_id = str(queue_resp.get("task_id", "")).strip()
        if not task_id:
            raise SmokeError(f"queue_move did not return task_id: {queue_resp}")

        print(f"      Published task_id={task_id}")

        print("[6/7] Waiting ACK for published task...")
        ack_payload = _wait_for_ack(
            base_url=base_url,
            device_id=device_id,
            task_id=task_id,
            timeout_sec=args.ack_timeout_sec,
            poll_interval_sec=args.poll_interval_sec,
            require_ok=not args.allow_ack_non_ok,
        )

        print("[7/7] Fetching latest MQTT events...")
        events = _http_json(
            "GET",
            _url(base_url, "/mqtt/events?limit=10"),
            None,
            args.http_timeout_sec,
        )

        result = {
            "ok": True,
            "base_url": base_url,
            "device_id": device_id,
            "task_id": task_id,
            "ack": ack_payload,
            "mqtt_event_count": events.get("count"),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("SMOKE TEST PASSED")
        return 0

    except SmokeError as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        return 1

    finally:
        tail = _stop_remote_agent(remote_proc)
        if tail:
            print("[remote-agent-tail]")
            for line in tail:
                print(line)


if __name__ == "__main__":
    raise SystemExit(main())
