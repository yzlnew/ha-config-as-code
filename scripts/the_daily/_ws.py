"""Tiny WebSocket client for HA. Reuses ha_api credentials."""

from __future__ import annotations

import json
import os as _os
import ssl
import sys as _sys

# Ensure sibling absolute imports work no matter how this module is loaded.
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_SCRIPTS = _os.path.dirname(_HERE)
for _p in (_HERE, _SCRIPTS):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import _bootstrap  # noqa: F401  -- loads .env, sets sys.path
import websocket  # websocket-client
import ha_api  # type: ignore


def ws_url() -> str:
    base = ha_api.HA_URL
    if base.startswith("https://"):
        return "wss://" + base[len("https://"):] + "/api/websocket"
    if base.startswith("http://"):
        return "ws://" + base[len("http://"):] + "/api/websocket"
    raise ValueError(f"Unsupported HA_URL scheme: {base}")


class WSClient:
    """One WS connection, auth handshake done in __init__, request() sends + matches by id."""

    def __init__(self, timeout: int = 15):
        self.ws = websocket.create_connection(
            ws_url(), timeout=timeout, sslopt={"cert_reqs": ssl.CERT_NONE}
        )
        # auth_required → auth → auth_ok
        first = json.loads(self.ws.recv())
        if first.get("type") != "auth_required":
            raise RuntimeError(f"Unexpected first WS message: {first}")
        self.ws.send(json.dumps({"type": "auth", "access_token": ha_api.TOKEN}))
        ack = json.loads(self.ws.recv())
        if ack.get("type") != "auth_ok":
            self.close()
            raise RuntimeError(f"WS auth failed: {ack}")
        self._id = 0

    def request(self, payload: dict) -> dict:
        """Send a message with auto-incrementing id; return the matched response."""
        self._id += 1
        msg = {**payload, "id": self._id}
        self.ws.send(json.dumps(msg))
        # Drain until we see our id (HA may interleave events on subscriptions)
        while True:
            resp = json.loads(self.ws.recv())
            if resp.get("id") == self._id:
                return resp

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
