#!/usr/bin/env python3
"""Compare executable YAML lines across paired e-paper firmware files."""

from __future__ import annotations

import argparse
import difflib
from pathlib import Path


PAIRS = {
    "bw": (
        Path("firmware/epaper-bw.yaml"),
        Path("esphome/trmnl_dashboard.yaml"),
    ),
    "e6": (
        Path("firmware/epaper-e6.yaml"),
        Path("esphome/xiao-epaper-e6.yaml"),
    ),
}


def executable_lines(path: Path) -> list[str]:
    """Return YAML content excluding blank and full-line comment rows."""
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        rows.append(raw.rstrip())
    return rows


def compare_pair(
    name: str,
    dashboard_root: Path,
    ha_root: Path,
) -> bool:
    dashboard_rel, ha_rel = PAIRS[name]
    dashboard_path = dashboard_root / dashboard_rel
    ha_path = ha_root / ha_rel
    for path in (dashboard_path, ha_path):
        if not path.is_file():
            raise FileNotFoundError(f"missing mapped firmware: {path}")

    dashboard_rows = executable_lines(dashboard_path)
    ha_rows = executable_lines(ha_path)
    if dashboard_rows == ha_rows:
        print(f"[sync] {name}: executable YAML matches")
        return True

    print(f"[sync] {name}: executable YAML differs")
    print("\n".join(difflib.unified_diff(
        dashboard_rows,
        ha_rows,
        fromfile=str(dashboard_path),
        tofile=str(ha_path),
        lineterm="",
    )))
    return False


def parser() -> argparse.ArgumentParser:
    default_ha_root = Path(__file__).resolve().parents[4]
    result = argparse.ArgumentParser(
        description="Check paired e-paper ESPHome firmware for semantic drift.",
    )
    result.add_argument(
        "--pair",
        choices=("all", *PAIRS),
        default="all",
    )
    result.add_argument(
        "--dashboard-root",
        type=Path,
        default=Path("/root/epaper-dashboard"),
    )
    result.add_argument(
        "--ha-root",
        type=Path,
        default=default_ha_root,
    )
    return result


def main() -> int:
    args = parser().parse_args()
    names = tuple(PAIRS) if args.pair == "all" else (args.pair,)
    matches = [
        compare_pair(name, args.dashboard_root.resolve(), args.ha_root.resolve())
        for name in names
    ]
    return 0 if all(matches) else 1


if __name__ == "__main__":
    raise SystemExit(main())
