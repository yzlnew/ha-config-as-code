#!/usr/bin/env python3
"""Fetch an online photo and process it into an 800x480 1-bit frame for the panel.

Used by cycle.py for the "photo frame" half of the alternating dashboard/photo
rotation. Photos (unlike text) MUST be dithered for 1-bit e-ink, so this center-fits
to 800x480, boosts contrast, and Floyd–Steinberg dithers to mode "1".

Source via EINK_PHOTO_SOURCE:
  bing   — Bing daily wallpaper, random from the last 8 days (scenic, no key) [default]
  picsum — Lorem Picsum, a different random photo every fetch (no key)

Network failures raise; cycle.py catches and falls back to the dashboard so the panel
never shows a blank/error frame.
"""

from __future__ import annotations

import io
import os
import random

import requests
from PIL import Image, ImageEnhance, ImageOps

W, H = 800, 480
UA = {"User-Agent": "Mozilla/5.0 (eink-frame)"}


def _process(data: bytes) -> Image.Image:
    im = Image.open(io.BytesIO(data)).convert("RGB")
    im = ImageOps.fit(im, (W, H), Image.LANCZOS)          # center-crop to fill
    g = im.convert("L")
    g = ImageOps.autocontrast(g, cutoff=1)                # use the full tonal range
    g = ImageEnhance.Contrast(g).enhance(1.12)            # photos dither better with a touch more contrast
    return g.convert("1", dither=Image.FLOYDSTEINBERG)


def _bing() -> tuple[Image.Image, str]:
    idx = random.randint(0, 7)  # last 8 days of dailies → within-day variety
    r = requests.get(
        "https://www.bing.com/HPImageArchive.aspx",
        params={"format": "js", "idx": idx, "n": 1, "mkt": "zh-CN"},
        headers=UA, timeout=12,
    )
    r.raise_for_status()
    info = r.json()["images"][0]
    url = "https://www.bing.com" + info["url"]
    img = requests.get(url, headers=UA, timeout=25)
    img.raise_for_status()
    title = (info.get("copyright") or "").split("(")[0].strip()
    return _process(img.content), title


def _picsum() -> tuple[Image.Image, str]:
    r = requests.get(f"https://picsum.photos/{W}/{H}", headers=UA, timeout=25)
    r.raise_for_status()
    return _process(r.content), ""


PROVIDERS = {"bing": _bing, "picsum": _picsum}


def fetch_frame() -> tuple[Image.Image, str]:
    """Return (800x480 mode-"1" image, caption). Raises on failure."""
    src = (os.getenv("EINK_PHOTO_SOURCE") or "bing").lower()
    provider = PROVIDERS.get(src, _bing)
    return provider()


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="scripts/eink/out/frame.png")
    args = ap.parse_args()
    frame, title = fetch_frame()
    frame.save(args.out)
    print(f"[photo] wrote {args.out}  source={os.getenv('EINK_PHOTO_SOURCE') or 'bing'}  title={title!r}")
