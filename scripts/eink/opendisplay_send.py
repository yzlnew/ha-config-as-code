#!/usr/bin/env python3
"""OpenDisplay BLE sender — push the rendered dashboard to an OpenDisplay panel.

This is the alternative to the ESPHome `online_image` path: instead of the panel
pulling a PNG over WiFi, HA (this script) renders the image and PUSHES it to the
panel over Bluetooth LE using the official py-opendisplay SDK.

Use this once the panel is flashed with OpenDisplay firmware (see README "OpenDisplay
firmware" section). The SDK is BLE-only, so run this on a host with a Bluetooth
adapter within ~10 m of the panel (the HA host qualifies — bluetooth integration
is active).

Usage:
  set -a && source .env && set +a

  # 1. Discover the panel's BLE MAC (after flashing OpenDisplay):
  .venv/bin/python scripts/eink/opendisplay_send.py --discover

  # 2. Render + push (set OPENDISPLAY_MAC, and OPENDISPLAY_KEY if BLE encryption on):
  OPENDISPLAY_MAC=AA:BB:CC:DD:EE:FF .venv/bin/python scripts/eink/opendisplay_send.py

Env:
  OPENDISPLAY_MAC  panel BLE MAC address (required for push)
  OPENDISPLAY_KEY  BLE encryption key as hex (optional; only if set in the Toolbox)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render  # noqa: E402  (reuse the exact same renderer as the ESPHome path)

from opendisplay import (  # noqa: E402
    OpenDisplayDevice,
    discover_devices,
    DitherMode,
    RefreshMode,
)


def build_image():
    """Render the dashboard PIL image (same content as the ESPHome PNG)."""
    states = render.fetch_states()
    news = render.fetch_news()
    img = render.render(states, news)
    print(f"[od] rendered {img.size} mode={img.mode}  states={len(states)} news={len(news)}")
    return img


async def cmd_discover(timeout: float) -> int:
    print(f"[od] scanning for OpenDisplay devices ({timeout:.0f}s)…")
    found = await discover_devices(timeout=timeout)
    if not found:
        print("[od] none found. Is the panel flashed with OpenDisplay firmware and in range?")
        return 1
    for name, mac in found.items():
        print(f"[od]   {name}  →  {mac}")
    print("[od] set OPENDISPLAY_MAC to the MAC above, then run without --discover.")
    return 0


async def cmd_push(mac: str, key_hex: str | None) -> int:
    img = build_image()  # rendered before connecting to minimize BLE hold time
    key = bytes.fromhex(key_hex) if key_hex else None
    print(f"[od] connecting to {mac}…")
    async with OpenDisplayDevice(mac_address=mac, encryption_key=key) as dev:
        fw = await dev.read_firmware_version()
        print(f"[od] connected. firmware={fw}")
        # Image is already crisp 1-bit black/white; skip dithering, full refresh.
        await dev.upload_image(img, refresh_mode=RefreshMode.FULL, dither_mode=DitherMode.NONE)
    print("[od] image pushed.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--discover", action="store_true", help="scan for OpenDisplay panels and print MACs")
    ap.add_argument("--timeout", type=float, default=10.0, help="BLE scan timeout (with --discover)")
    args = ap.parse_args()

    if args.discover:
        return asyncio.run(cmd_discover(args.timeout))

    mac = os.environ.get("OPENDISPLAY_MAC")
    if not mac:
        print("[od] OPENDISPLAY_MAC not set. Run with --discover first.", file=sys.stderr)
        return 2
    return asyncio.run(cmd_push(mac, os.environ.get("OPENDISPLAY_KEY")))


if __name__ == "__main__":
    raise SystemExit(main())
