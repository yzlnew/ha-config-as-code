#!/usr/bin/env python3
"""Render the 800x480 1-bit e-ink dashboard PNG that HA serves to the TRMNL panel.

Architecture (server-side rendering): this script pulls live HA state + FreshRSS
news, composes a 1-bit image with Pillow, and writes it to OUT_PATH. deploy.py SCPs
it to HA's /config/www/eink/dashboard.png, and the ESPHome `online_image` component
on the panel downloads + displays it.

Design: the **Nothing UI** design system. White canvas with floating rounded
tiles (radius ≤16, 1px borders); **Doto** dot-matrix numerals for hero values
(clock, date, temps, %); Space Mono ALL-CAPS labels and news titles; Noto Sans SC
for Chinese. The date (top-right) and air (bottom-middle) tiles are inverted into
solid black "interrupt" accents. We draw white; EINK_INVERT flips it so the panel,
which inverts again, shows a white background.

Standalone-friendly: runs on any machine with Pillow + network access to HA.
Missing sensors render as "--"; FreshRSS failures degrade to 暂无新闻.

Run:
  set -a && source .env && set +a
  .venv/bin/python scripts/eink/render.py [--out PATH] [--invert]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
FONT_DIR = REPO / "esphome" / "fonts"
OUT_PATH = HERE / "out" / "dashboard.png"

W, H = 800, 480
# Doto's dots render crispest at NATIVE resolution — supersampling + downscale erodes
# them into hollow/ragged rings. Draw on an L canvas at 1x (antialiased) then threshold.
SS = 1

HA_URL = (os.getenv("HA_URL") or os.getenv("HA_EXTERNAL_URL") or "").rstrip("/")
HA_TOKEN = os.getenv("HA_TOKEN") or ""

# ── Entity IDs (mirror esphome/trmnl_dashboard.yaml) ─────────────────────────
ENT = {
    "temp": "sensor.xiaomi_cn_2008215373_ua3a_temperature_p_3_7",
    "humidity": "sensor.xiaomi_cn_2008215373_ua3a_relative_humidity_p_3_1",
    "pm25": "sensor.xiaomi_cn_2008215373_ua3a_pm2_5_density_p_3_4",
    "co2": "sensor.xiaomi_cn_2008215373_ua3a_co2_density_p_3_8",
    "hcho": "sensor.xiaomi_cn_2008215373_ua3a_hcho_density_p_3_10",  # mg/m³
    "lock_batt": "sensor.lumi_cn_1011935590_bzacn1_battery_level_p_4_1",
    "weather": "weather.forecast_wo_de_jia",
    "cat_waste": "binary_sensor.zhi_neng_mao_ce_suo_max_wastebin_filled",
    "cat_sand": "binary_sensor.zhi_neng_mao_ce_suo_max_sand_lack",
    "water_lack": "binary_sensor.yin_shui_ji_max_zhen_wu_xian_water_lack_warning",
}

WEATHER_CN = {
    "sunny": "晴", "clear-night": "晴", "partlycloudy": "多云", "cloudy": "阴",
    "rainy": "小雨", "pouring": "大雨", "snowy": "雪", "fog": "雾",
    "lightning": "雷阵雨", "lightning-rainy": "雷雨", "windy": "大风",
    "windy-variant": "大风", "hail": "冰雹", "exceptional": "异常",
}
# which dot-icon to draw for each condition
WEATHER_ICON = {
    "sunny": "sun", "clear-night": "moon", "partlycloudy": "cloud", "cloudy": "cloud",
    "rainy": "rain", "pouring": "rain", "snowy": "snow", "fog": "cloud",
    "lightning": "rain", "lightning-rainy": "rain", "windy": "cloud",
    "windy-variant": "cloud", "hail": "rain",
}
EN_WD = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
EN_MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


# ── HA data ──────────────────────────────────────────────────────────────────
def fetch_states() -> dict[str, dict]:
    if not HA_URL or not HA_TOKEN:
        print("[render] HA_URL/HA_TOKEN not set — rendering with placeholders", file=sys.stderr)
        return {}
    try:
        r = requests.get(f"{HA_URL}/api/states",
                         headers={"Authorization": f"Bearer {HA_TOKEN}"}, timeout=12)
        r.raise_for_status()
        return {s["entity_id"]: s for s in r.json()}
    except Exception as exc:  # noqa: BLE001
        print(f"[render] states fetch failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return {}


def _state(states: dict, key: str) -> str | None:
    s = states.get(ENT[key])
    if not s:
        return None
    v = s.get("state")
    return None if v in (None, "unknown", "unavailable", "") else v


def _attr(states: dict, key: str, attr: str) -> float | None:
    s = states.get(ENT[key])
    if not s:
        return None
    v = s.get("attributes", {}).get(attr)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _num(v, fmt: str = "%.1f") -> str:
    try:
        return fmt % float(v)
    except (TypeError, ValueError):
        return "--"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ── News (FreshRSS, optional) ────────────────────────────────────────────────
def fetch_news(limit: int = 6) -> list[dict]:
    try:
        sys.path.insert(0, str(REPO / "scripts" / "the_daily"))
        import freshrss_bridge  # type: ignore

        items, _ = freshrss_bridge.fetch_top(limit=limit, pad=True)
        return items or []
    except Exception as exc:  # noqa: BLE001
        print(f"[render] news unavailable ({type(exc).__name__}); skipping", file=sys.stderr)
        return []


def _ellipsize(font, text, max_w):
    if font.getlength(text) <= max_w:
        return text
    while text and font.getlength(text + "…") > max_w:
        text = text[:-1]
    return text + "…"


# ── Compose ──────────────────────────────────────────────────────────────────
def render(states: dict, news: list[dict]) -> Image.Image:
    now = datetime.now()
    s = SS
    big = Image.new("L", (W * s, H * s), 255)  # white canvas (date + air tiles inverted to black later)
    d = ImageDraw.Draw(big)

    DOTO, MONO, MONOB, SANS = "Doto.ttf", "SpaceMono-Regular.ttf", "SpaceMono-Bold.ttf", "NotoSansSC.ttf"

    def doto(px, wght=800, rnd=100):
        ft = ImageFont.truetype(str(FONT_DIR / DOTO), int(px * s))
        try:
            ft.set_variation_by_axes([rnd, wght])
        except Exception:
            pass
        return ft

    def fnt(name, px, wght=None):
        ft = ImageFont.truetype(str(FONT_DIR / name), int(px * s))
        if wght is not None:
            try:
                ft.set_variation_by_axes([wght])
            except Exception:
                pass
        return ft

    LAB = fnt(MONO, 13)
    LABB = fnt(MONOB, 13)
    CJK = fnt(SANS, 15, 500)
    CJKS = fnt(SANS, 12, 500)
    CJKW = fnt(SANS, 30, 600)
    NEWS = fnt(SANS, 14, 400)

    INK, BG = 0, 255  # black ink on white canvas

    # ── draw helpers (final-px coords) ──
    def text(x, y, t, font, fill=INK, anchor=None):
        d.text((x * s, y * s), t, font=font, fill=fill, anchor=anchor)

    def tw(t, font):
        return font.getlength(t) / s

    def fit_doto(t, max_w, sizes):
        for sz in sizes:
            f = doto(sz)
            if tw(t, f) <= max_w:
                return f, sz
        return doto(sizes[-1]), sizes[-1]

    def tile(x, y, w, h, r=16):
        d.rounded_rectangle([x * s, y * s, (x + w) * s, (y + h) * s], radius=int(r * s),
                            outline=INK, width=max(1, int(1 * s)))

    def pill(x, y, w, h, t, font):  # filled "interrupt" highlight (stands in for red)
        d.rounded_rectangle([x * s, y * s, (x + w) * s, (y + h) * s], radius=int(h / 2 * s), fill=INK)
        text(x + w / 2, y + h / 2, t, font, fill=BG, anchor="mm")

    def dotsicon(cx, cy, kind, R=18):  # small white dot-icon, Nothing style
        def dt(px, py, rr=2.6):
            d.ellipse([(px - rr) * s, (py - rr) * s, (px + rr) * s, (py + rr) * s], fill=INK)
        if kind == "sun":
            dt(cx, cy, 6)
            for a in range(0, 360, 45):
                import math
                dt(cx + math.cos(math.radians(a)) * R, cy + math.sin(math.radians(a)) * R, 2.4)
        elif kind == "moon":
            for a in range(40, 320, 28):
                import math
                dt(cx + math.cos(math.radians(a)) * R, cy + math.sin(math.radians(a)) * R, 2.6)
        elif kind in ("cloud", "snow"):
            for (px, py, rr) in [(cx - 9, cy + 2, 5), (cx + 1, cy - 4, 6.5), (cx + 11, cy + 2, 5),
                                 (cx - 3, cy + 4, 5), (cx + 7, cy + 4, 5)]:
                dt(px, py, rr)
        elif kind == "rain":
            for (px, py, rr) in [(cx - 8, cy - 3, 5), (cx + 2, cy - 7, 6), (cx + 10, cy - 3, 5)]:
                dt(px, py, rr)
            for px in (cx - 6, cx + 2, cx + 10):
                dt(px, cy + 8, 2.2); dt(px, cy + 14, 2.2)

    def ring(cx, cy, R, ratio, w=6):
        import math
        bb = [(cx - R) * s, (cy - R) * s, (cx + R) * s, (cy + R) * s]
        # faint full track (dotted)
        for a in range(0, 360, 12):
            d.ellipse([(cx + math.cos(math.radians(a)) * R - 1.3) * s,
                       (cy + math.sin(math.radians(a)) * R - 1.3) * s,
                       (cx + math.cos(math.radians(a)) * R + 1.3) * s,
                       (cy + math.sin(math.radians(a)) * R + 1.3) * s], fill=INK)
        end = -90 + max(0.0, min(1.0, ratio)) * 360
        d.arc(bb, -90, end, fill=INK, width=max(1, int(w * s)))

    GAP, M = 16, 20

    # ════════ TOP ROW ════════
    ty, th = 20, 206
    # CLOCK tile
    cx, cw = M, 326
    tile(cx, ty, cw, th)
    text(cx + 22, ty + 18, "NOW", LAB)
    tstr = now.strftime("%H:%M")
    cf, _ = fit_doto(tstr, cw - 40, [112, 104, 96, 88])
    text(cx + cw / 2, ty + th / 2 + 6, tstr, cf, anchor="mm")
    text(cx + 22, ty + th - 30, f"{EN_WD[now.isoweekday()-1]} · {now.year}-{now.month:02d}-{now.day:02d}", LAB)

    # WEATHER tile
    wx, ww = cx + cw + GAP, 196
    tile(wx, ty, ww, th)
    text(wx + 20, ty + 18, "WEATHER", LAB)
    wstate = _state(states, "weather") or "cloudy"
    dotsicon(wx + 44, ty + 70, WEATHER_ICON.get(wstate, "cloud"), R=18)
    wt = _num(_attr(states, "weather", "temperature"), "%.0f")
    wf, _ = fit_doto(f"{wt}°", ww - 40, [64, 56, 48])
    text(wx + 20, ty + 104, f"{wt}°", wf)
    text(wx + 20, ty + th - 44, WEATHER_CN.get(wstate, "--"), CJKW)

    # CALENDAR tile (AUG / THU / 28) — black accent (inverted at the end)
    lx, lw = wx + ww + GAP, W - M - (wx + ww + GAP)
    text(lx + 20, ty + 18, EN_MON[now.month - 1], LAB)
    pw = tw(EN_WD[now.isoweekday() - 1], LABB) + 26
    pill(lx + lw - 20 - pw, ty + 14, pw, 22, EN_WD[now.isoweekday() - 1], LABB)
    df, _ = fit_doto(f"{now.day:02d}", lw - 40, [120, 110, 100])
    text(lx + lw / 2, ty + th / 2 + 18, f"{now.day:02d}", df, anchor="mm")

    # ════════ BOTTOM ROW ════════
    by, bh = ty + th + GAP, H - (ty + th + GAP) - M
    # HOME tile (temp + hum, units in labels; device status)
    hx, hw = M, 248
    tile(hx, by, hw, bh)
    text(hx + 22, by + 16, "HOME", LAB)
    temp = _num(_state(states, "temp"))
    hum = _num(_state(states, "humidity"), "%.0f")
    text(hx + 22, by + 46, "TEMP °C", LAB)
    tf, _ = fit_doto(temp, 104, [44, 40, 36])
    text(hx + 22, by + 64, temp, tf)
    text(hx + 138, by + 46, "HUM %", LAB)
    hf, _ = fit_doto(hum, 96, [44, 40, 36])
    text(hx + 138, by + 64, hum, hf)
    # device status row
    lb = _f(_state(states, "lock_batt")) or 0
    cat = "FULL" if (states.get(ENT["cat_waste"], {}).get("state") == "on") else (
        "LOW" if states.get(ENT["cat_sand"], {}).get("state") == "on" else "OK")
    water = "LOW" if states.get(ENT["water_lack"], {}).get("state") == "on" else "OK"
    text(hx + 22, by + bh - 58, f"LOCK   {lb:.0f}%", LAB)
    text(hx + 22, by + bh - 40, f"LITTER {cat}", LAB)
    text(hx + 22, by + bh - 22, f"WATER  {water}", LAB)

    # AIR tile (HCHO ring gauge + PM2.5/CO2 small text) — black accent (inverted at the end)
    ax, aw = hx + hw + GAP, 188
    text(ax + 20, by + 16, "AIR", LAB)
    pm = _f(_state(states, "pm25"))
    co = _f(_state(states, "co2"))
    hcho = _f(_state(states, "hcho"))
    hug = hcho * 1000 if hcho is not None else None   # mg/m³ → µg/m³ integer
    over = hug is not None and hug > 80               # GB/T 18883 limit 0.08 mg/m³
    ring(ax + aw / 2, by + 90, 52, (hug or 0) / 100, w=7)
    rtxt = _num(hug, "%.0f") + ("!" if over else "")
    rf, _ = fit_doto(rtxt, 84, [40, 34, 28])
    text(ax + aw / 2, by + 90, rtxt, rf, anchor="mm")
    text(ax + aw / 2, by + 144, "甲醛 μg/m³", CJKS, anchor="ma")
    text(ax + 20, by + bh - 44, f"PM2.5 {_num(pm, '%.0f')}", LAB)
    text(ax + 20, by + bh - 22, f"CO2   {_num(co, '%.0f')} PPM", LAB)

    # NEWS tile — normal outlined tile; titles in Space Mono (same face as the
    # NEWS label), with per-char Noto Sans SC fallback for CJK.
    nx = ax + aw + GAP
    nw = W - M - nx
    tile(nx, by, nw, bh)
    text(nx + 20, by + 16, "NEWS", LAB)
    NM = fnt(MONO, 14)        # Space Mono title face (matches NEWS label)
    NC = fnt(SANS, 14, 500)   # CJK fallback
    limit_w = nx + nw - 16
    ny = by + 52
    if not news:
        text(nx + 20, ny, "NO FEED", NM, anchor="lm")
    for it in news[:4]:
        if ny > by + bh - 16:
            break
        text(nx + 18, ny, "·", LABB, anchor="lm")
        cx = nx + 34
        for ch in (it.get("title") or ""):
            f = NM if ch.isascii() else NC
            chw = f.getlength(ch) / s
            if cx + chw > limit_w - 8:
                text(cx, ny, "…", NM, anchor="lm")
                break
            text(cx, ny, ch, f, anchor="lm")
            cx += chw
        ny += 30

    # ── accent tiles: invert the date + air regions into solid black blocks ──
    def accent(x, y, w, h, r=16):
        x0, y0, x1, y1 = int(x * s), int(y * s), int((x + w) * s), int((y + h) * s)
        region = big.crop((x0, y0, x1, y1))
        mask = Image.new("1", region.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, region.size[0] - 1, region.size[1] - 1], radius=int(r * s), fill=1)
        big.paste(region.point(lambda p: 255 - p), (x0, y0), mask)

    accent(lx, ty, lw, th)   # date (top-right) → black accent
    accent(ax, by, aw, bh)   # air (bottom-middle) → black accent

    img = big.resize((W, H), Image.LANCZOS).convert("1")
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT_PATH))
    ap.add_argument("--invert", action="store_true",
                    default=os.getenv("EINK_INVERT") == "1",
                    help="invert black/white — use if the panel shows a black background "
                         "(ESPHome online_image maps the PNG inverted). Also via EINK_INVERT=1.")
    args = ap.parse_args()

    states = fetch_states()
    news = fetch_news()
    img = render(states, news)
    if args.invert:
        # ImageChops.invert mangles mode "1" (yields 254/255); invert in L space.
        img = img.convert("L").point(lambda p: 255 - p).convert("1")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"[render] wrote {out} ({out.stat().st_size} bytes)  states={len(states)} news={len(news)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
