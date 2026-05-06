"""Orchestrator: pulls HA + FreshRSS data, writes /root/ha/www/the-daily/data.json.

Run: cd /root/ha && .venv/bin/python scripts/the_daily/compose.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os as _os
import sys
import sys as _sys
import traceback
from datetime import datetime
from pathlib import Path

_HERE = _os.path.dirname(_os.path.abspath(__file__))
_SCRIPTS = _os.path.dirname(_HERE)
for _p in (_HERE, _SCRIPTS):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import _bootstrap  # noqa: F401
import sources
import freshrss_bridge
from _ws import WSClient

import ha_api  # type: ignore


OUT_PATH = Path("/root/ha/www/the-daily/data.json")


def build_data() -> tuple[dict, bool]:
    """Returns (data, ok). ok=False means at least one critical fetcher failed."""
    ok = True
    data: dict = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "edition": sources.edition_string(datetime.now()),
        "masthead": {"left": "Home Assistant · all systems", "status_dot": "ok"},
    }

    # Fetch /api/states once — most fetchers reuse it
    states_list: list[dict] = []
    states_dict: dict[str, dict] = {}
    try:
        states_list = sources._states()
        states_dict = sources._by_id(states_list)
    except Exception as exc:
        print(f"[states] {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        ok = False
        data["masthead"] = {"left": "Home Assistant · unreachable", "status_dot": "error"}

    # Submeta lead + sunset
    try:
        lead = sources.fetch_lead(states_dict) if states_dict else {"lead": "—", "stamp_suffix": ""}
        data["submeta"] = lead
    except Exception as exc:
        print(f"[lead] {exc}", file=sys.stderr)
        data["submeta"] = {"lead": "—", "stamp_suffix": ""}
        ok = False

    # Tiles (rely on states)
    house = sources.fetch_house(states_list) if states_list else {"value": None, "subscript": "—", "meta": "—", "meter_on": 0, "meter_total": 8, "rows": [], "lights_on": 0}
    climate = sources.fetch_climate(states_dict) if states_dict else {"value": None, "subscript": "—", "meta": "—", "caption": "—", "rows": [], "living_temp": None}
    air = sources.fetch_air(states_dict) if states_dict else {"value": None, "subscript": "—", "meta": "—", "caption": "—", "rows": [], "pm25": None, "humidity": None, "temperature": None}
    energy = sources.fetch_energy(states_dict) if states_dict else {"value": None, "subscript": "kWh", "meta": "—", "bars": [], "rows": []}

    data["tiles"] = {
        "house": {k: v for k, v in house.items() if k not in ("lights_on", "lights_total")},
        "climate": {k: v for k, v in climate.items() if k != "living_temp"},
        "air": {k: v for k, v in air.items() if k not in ("pm25", "humidity", "temperature")},
        "energy": energy,
    }

    # Today prose + quick stats
    try:
        prose_html = sources.fetch_today_prose(house, climate, air)
    except Exception as exc:
        print(f"[prose] {exc}", file=sys.stderr)
        prose_html = "—"
    data["today"] = {
        "prose_html": prose_html,
        "quick": {
            "lights_on": house.get("lights_on") if states_list else None,
            "air": air.get("pm25"),
            "kwh": energy.get("value"),
        },
    }

    # Calendar (REST)
    try:
        data["calendar"] = sources.fetch_calendar()
    except Exception as exc:
        print(f"[calendar] {exc}", file=sys.stderr)
        data["calendar"] = {"label_meta": "—", "events": []}

    # Tasks + Bulletin via WebSocket (one connection)
    tasks_data: dict = {"label_meta": "—", "items": [], "source": "—"}
    bulletin_items: list[dict] = []
    bulletin_count = 0
    ws: WSClient | None = None
    try:
        ws = WSClient()
        tasks_data = sources.fetch_tasks(ws)
        bulletin_items, bulletin_count = sources.fetch_bulletin(ws)
    except Exception as exc:
        print(f"[ws] {type(exc).__name__}: {exc}", file=sys.stderr)
        ok = False
    finally:
        if ws:
            ws.close()
    data["tasks"] = tasks_data

    # FreshRSS Wire
    headlines, total_unread = freshrss_bridge.fetch_top(limit=6)

    data["wire"] = {
        "headlines": headlines,
        "headlines_unread": total_unread or len(headlines),
        "social": [],
        "social_count": 0,
        "bulletin": bulletin_items,
        "bulletin_count": bulletin_count,
        "sources_count": (1 if headlines else 0) + (1 if bulletin_items else 0),
    }

    # Footer
    try:
        sys_str = sources.fetch_system_summary(states_dict)
    except Exception:
        sys_str = "Home Assistant"
    data["footer"] = {"system": sys_str}

    return data, ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Compose The Daily data.json")
    parser.add_argument("--dry-run", action="store_true", help="print JSON to stdout instead of writing")
    parser.add_argument("--out", default=str(OUT_PATH), help=f"output path (default: {OUT_PATH})")
    args = parser.parse_args()

    data, ok = build_data()
    payload = json.dumps(data, ensure_ascii=False, indent=2)

    if args.dry_run:
        print(payload)
        return 0 if ok else 2

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload + "\n", encoding="utf-8")
    print(f"[compose] wrote {out} ({len(payload)} bytes, ok={ok})")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
