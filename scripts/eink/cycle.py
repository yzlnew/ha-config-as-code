#!/usr/bin/env python3
"""Alternate the panel between the dashboard and an online photo frame each refresh.

The panel always pulls one URL (/local/eink/dashboard.png); this script decides what
that PNG *is* on each run. Strict alternation (dashboard → photo → dashboard …) is
tracked in a tiny state file, since each cron run is independent.

Both outputs get the same invert treatment (EINK_INVERT=1) — the panel inverts
everything it shows, so we pre-invert: a pre-inverted dashboard reads correctly, and
a pre-inverted photo + the panel's invert cancel back to a normal (non-negative) photo.

If the online photo fetch fails, falls back to the dashboard so the panel never shows
a blank/error frame.

Run (replaces render.py in the cron):
  set -a && source .env && set +a
  .venv/bin/python scripts/eink/cycle.py && .venv/bin/python scripts/eink/deploy.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import photo  # noqa: E402  (local module)
import render  # noqa: E402

STATE = HERE / "out" / ".last_mode"


def _invert(img):
    # ImageChops.invert mangles mode "1" (254/255); invert in L space.
    return img.convert("L").point(lambda p: 255 - p).convert("1")


def main() -> int:
    last = STATE.read_text().strip() if STATE.exists() else "photo"
    mode = "photo" if last == "dashboard" else "dashboard"  # strict alternate

    img = None
    if mode == "photo":
        try:
            img, title = photo.fetch_frame()
            print(f"[cycle] photo source={os.getenv('EINK_PHOTO_SOURCE') or 'bing'} title={title!r}")
        except Exception as exc:  # noqa: BLE001
            print(f"[cycle] photo fetch failed ({type(exc).__name__}: {exc}); "
                  f"falling back to dashboard", file=sys.stderr)
            mode = "dashboard"
    if img is None:  # dashboard, or photo-fallback
        img = render.render(render.fetch_states(), render.fetch_news())

    if os.getenv("EINK_INVERT") == "1":
        img = _invert(img)

    out = render.OUT_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    STATE.write_text(mode)
    print(f"[cycle] mode={mode} → {out} ({out.stat().st_size}B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
