#!/usr/bin/env python3
"""Set up an RTSP camera in Home Assistant via config flow API + WebSocket."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import requests
import websocket

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


def load_env() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    env_file = repo_root / ".env"
    if not env_file.exists():
        return
    if load_dotenv:
        load_dotenv(env_file)
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"[ERROR] Missing environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return value or "rtsp_camera"


def inject_credentials(rtsp_url: str, username: str, password: str) -> str:
    parts = urlsplit(rtsp_url)
    if not parts.scheme or not parts.hostname:
        print("[ERROR] Invalid RTSP URL", file=sys.stderr)
        sys.exit(1)
    host = parts.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{quote(username, safe='')}:{quote(password, safe='')}@{host}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def ha_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def create_generic_camera(
    base_url: str, token: str, stream_source: str
) -> dict:
    """Create a generic camera integration via config flow API."""
    headers = ha_headers(token)

    # Step 1: Start config flow
    resp = requests.post(
        f"{base_url}/api/config/config_entries/flow",
        headers=headers,
        json={"handler": "generic"},
    )
    resp.raise_for_status()
    flow = resp.json()
    flow_id = flow["flow_id"]
    print(f"  [OK] config flow started: {flow_id}")

    # Step 2: Submit stream config
    resp = requests.post(
        f"{base_url}/api/config/config_entries/flow/{flow_id}",
        headers=headers,
        json={
            "stream_source": stream_source,
            "still_image_url": "",
            "username": "",
            "password": "",
            "advanced": {
                "framerate": 2,
                "verify_ssl": False,
                "rtsp_transport": "tcp",
                "authentication": "basic",
            },
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        print(f"[ERROR] Config flow errors: {data['errors']}", file=sys.stderr)
        sys.exit(1)

    # Step 3: Confirm preview
    if data.get("step_id") == "user_confirm":
        resp = requests.post(
            f"{base_url}/api/config/config_entries/flow/{flow_id}",
            headers=headers,
            json={"confirmed_ok": True},
        )
        resp.raise_for_status()
        data = resp.json()

    if data.get("type") != "create_entry":
        print(f"[ERROR] Unexpected flow result: {data}", file=sys.stderr)
        sys.exit(1)

    return data["result"]


def ws_call(ws, msg_id: int, payload: dict) -> dict:
    """Send a WebSocket command and return the result."""
    payload["id"] = msg_id
    ws.send(json.dumps(payload))
    resp = json.loads(ws.recv())
    if not resp.get("success"):
        print(f"[ERROR] WS call failed: {resp}", file=sys.stderr)
        sys.exit(1)
    return resp


def configure_entity(
    base_url: str,
    token: str,
    config_entry_id: str,
    name: str,
    icon: str,
    area_id: str,
) -> None:
    """Rename entity, set icon, and assign device to area via WebSocket."""
    ws_url = base_url.replace("http", "ws", 1) + "/api/websocket"
    ws = websocket.create_connection(ws_url)
    ws.recv()  # auth_required
    ws.send(json.dumps({"type": "auth", "access_token": token}))
    ws.recv()  # auth_ok

    # Find entity for this config entry
    result = ws_call(ws, 2, {"type": "config/entity_registry/list"})
    entity = None
    device_id = None
    for e in result["result"]:
        if e.get("config_entry_id") == config_entry_id:
            entity = e
            device_id = e.get("device_id")
            break

    if not entity:
        print("[ERROR] Could not find entity for config entry", file=sys.stderr)
        ws.close()
        sys.exit(1)

    entity_id = entity["entity_id"]
    print(f"  [OK] found entity: {entity_id}")

    # Update entity name and icon
    ws_call(ws, 3, {
        "type": "config/entity_registry/update",
        "entity_id": entity_id,
        "name": name,
        "icon": icon,
    })
    print(f"  [OK] entity renamed to: {name}")

    # Assign device to area
    if device_id and area_id:
        ws_call(ws, 4, {
            "type": "config/device_registry/update",
            "device_id": device_id,
            "area_id": area_id,
        })
        print(f"  [OK] device assigned to area: {area_id}")

    ws.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set up an RTSP camera in Home Assistant via config flow API"
    )
    parser.add_argument("--name", default="RTSP Camera", help="Camera display name")
    parser.add_argument("--rtsp-url", required=True, help="RTSP URL (without credentials)")
    parser.add_argument("--username", required=True, help="RTSP username")
    parser.add_argument("--password", required=True, help="RTSP password")
    parser.add_argument("--icon", default="mdi:camera", help="Entity icon (default: mdi:camera)")
    parser.add_argument("--area-id", default="", help="Area ID to assign the camera to")
    return parser.parse_args()


def main() -> None:
    load_env()
    args = parse_args()

    base_url = require_env("HA_URL")
    token = require_env("HA_TOKEN")
    stream_source = inject_credentials(args.rtsp_url, args.username, args.password)

    print("=== RTSP Camera Setup (Config Flow) ===\n")
    print(f"Camera name : {args.name}")
    print(f"Stream      : {args.rtsp_url}")
    if args.area_id:
        print(f"Area        : {args.area_id}")

    # Verify API connectivity
    print("\n1. Verifying API connectivity...")
    resp = requests.get(f"{base_url}/api/", headers=ha_headers(token))
    resp.raise_for_status()
    print("  [OK] API reachable")

    # Create generic camera via config flow
    print("2. Creating generic camera integration...")
    entry = create_generic_camera(base_url, token, stream_source)
    entry_id = entry["entry_id"]
    print(f"  [OK] config entry created: {entry_id}")

    # Configure entity name, icon, and area
    print("3. Configuring entity...")
    configure_entity(base_url, token, entry_id, args.name, args.icon, args.area_id)

    print(f"\nDone. Camera '{args.name}' is ready (no restart needed).")


if __name__ == "__main__":
    main()
