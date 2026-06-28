#!/usr/bin/env python3
"""One-time OpenDisplay provisioning for the TRMNL 7.5" panel.

A freshly-flashed OpenDisplay device boots with an empty config (the Toolbox's
"Configure over Bluetooth" step). This writes the board/display/pin config for a
Waveshare/Xiao V2 7.5" 800x480 mono panel on the TRMNL pinout, then pushes the
first rendered image to verify. After this, recurring pushes use
opendisplay_send.py (which reads the now-stored config via interrogation).

Panel: ep75_800x480_gen2 (GEDY075-D2, panel_ic_type=59), e-paper, mono.
Pins (match esphome/trmnl_dashboard.yaml): clk7 mosi/data9 cs44 dc10 rst38 busy4.

Run:
  set -a && source .env && set +a
  .venv/bin/python scripts/eink/opendisplay_provision.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render  # noqa: E402

from opendisplay import OpenDisplayDevice, discover_devices, DitherMode, RefreshMode  # noqa: E402
from opendisplay.models.config_json import config_from_json  # noqa: E402

CONFIG_JSON = {
    "version": 1,
    "packets": [
        # 0x01 system: ESP32-S3, BLE comms
        {"id": "1", "fields": {"ic_type": "2", "communication_modes": "1", "device_flags": "0"}},
        # 0x02 manufacturer: DIY / custom board
        {"id": "2", "fields": {"manufacturer_id": "0", "board_type": "0"}},
        # 0x04 power: normal, no deep sleep (wall-powered, stay BLE-connectable)
        {"id": "4", "fields": {"power_mode": "0", "sleep_timeout_ms": "0"}},
        # 0x20 display: Waveshare/Xiao V2 7.5" 800x480 mono on TRMNL pins
        {"id": "32", "fields": {
            "instance_number": "0",
            "display_technology": "1",   # e-paper
            "panel_ic_type": "59",       # ep75_800x480_gen2 (GEDY075-D2)
            "pixel_width": "800",
            "pixel_height": "480",
            "active_width_mm": "163",
            "active_height_mm": "98",
            "rotation": "0",
            "reset_pin": "38",
            "busy_pin": "4",
            "dc_pin": "10",
            "cs_pin": "44",
            "data_pin": "9",             # MOSI
            "clk_pin": "7",
            "partial_update_support": "0",
            "color_scheme": "0",         # monochrome
            "transmission_modes": "0",   # raw (we push uncompressed for reliability)
        }},
    ],
}


async def main() -> int:
    print("[prov] scanning for OpenDisplay panel…")
    found = await discover_devices(timeout=20)
    od = {n: m for n, m in found.items() if n.upper().startswith("OD")}
    if not od:
        print(f"[prov] no OpenDisplay device found (saw: {found}). Is it powered + in range?", file=sys.stderr)
        return 1
    name, addr = next(iter(od.items()))
    print(f"[prov] device {name} → {addr}")

    cfg = config_from_json(CONFIG_JSON)
    print(f"[prov] built config: {len(cfg.displays)} display(s), panel_ic_type={cfg.displays[0].panel_ic_type}")

    img = render.render(render.fetch_states(), render.fetch_news())
    print(f"[prov] rendered {img.size} {img.mode}")

    # Pass config= to skip interrogation of the blank device.
    async with OpenDisplayDevice(mac_address=addr, config=cfg) as dev:
        print("[prov] connected; writing config…")
        await dev.write_config(cfg)
        print("[prov] config written. Uploading image (raw, full refresh)…")
        await dev.upload_image(img, refresh_mode=RefreshMode.FULL, dither_mode=DitherMode.NONE, compress=False)
    print("[prov] done — panel should now show the dashboard.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
