#!/usr/bin/env python3
"""Render the 800x480 SIX-COLOUR e-ink dashboard for the XIAO ESP32-S3 + GDEP073E01
(7.3" E Ink Spectra 6 / E6) panel.

Unlike render.py (1-bit mono, black canvas + invert for the TRMNL 7.5"), the E6 is a
true colour paper-white panel. So this design is inverted in spirit: a WHITE paper
background with coloured ink, where colour carries meaning:

    black  — primary text / numerals / structure
    red    — alerts & the "interrupt" accent (over-limit, low, full, hot)
    green  — healthy / OK status
    blue   — cool / water / time / info
    yellow — sun & warm-weather accent, mid-level caution
    white  — background

The E6 driver (esphome epaper_spi `color_to_hex`) only renders 6 solid colours; any
other RGB snaps to the nearest via a grayscale threshold + primary-corner test. To make
the preview PNG faithful to the panel, every pixel is pushed through quantize_to_e6(),
which mirrors that exact mapping. What you see == what the panel shows.

Run:
  set -a && source .env && set +a
  .venv/bin/python scripts/eink/render_e6.py [--out PATH] [--open]
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
FONT_DIR = REPO / "esphome" / "fonts"
OUT_PATH = HERE / "out" / "dashboard_e6.png"

W, H = 800, 480
SS = 2  # supersample for smoother CJK/curves, then downscale + quantize to 6 colours

HA_URL = (os.getenv("HA_URL") or os.getenv("HA_EXTERNAL_URL") or "").rstrip("/")
HA_TOKEN = os.getenv("HA_TOKEN") or ""

# ── The six E6 ink colours we draw with (source RGB, chosen to land cleanly in the
#    driver's colour buckets) and the muted RGB the real panel shows for each. ──────
INK = {
    "black":  (0, 0, 0),
    "white":  (255, 255, 255),
    "red":    (200, 0, 0),
    "green":  (0, 140, 0),
    "blue":   (0, 60, 190),
    "yellow": (235, 200, 0),
}
# Approximate on-panel appearance of each bucket (Spectra 6 is muted, not saturated).
PANEL_RGB = {
    "black":  (28, 28, 28),
    "white":  (244, 242, 236),   # paper isn't pure white
    "red":    (176, 42, 40),
    "green":  (58, 122, 74),
    "blue":   (46, 66, 150),
    "yellow": (222, 190, 60),
}

# ── Entity IDs (mirror render.py / esphome/trmnl_dashboard.yaml) ──────────────────
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
WEATHER_ICON = {
    "sunny": "sun", "clear-night": "moon", "partlycloudy": "cloud", "cloudy": "cloud",
    "rainy": "rain", "pouring": "rain", "snowy": "snow", "fog": "cloud",
    "lightning": "rain", "lightning-rainy": "rain", "windy": "cloud",
    "windy-variant": "cloud", "hail": "rain",
}
EN_WD = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
EN_MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


# ── HA data ──────────────────────────────────────────────────────────────────────
def fetch_states() -> dict[str, dict]:
    if not HA_URL or not HA_TOKEN:
        print("[render_e6] HA_URL/HA_TOKEN not set — placeholders", file=sys.stderr)
        return {}
    try:
        r = requests.get(f"{HA_URL}/api/states",
                         headers={"Authorization": f"Bearer {HA_TOKEN}"}, timeout=12, verify=False)
        r.raise_for_status()
        return {s["entity_id"]: s for s in r.json()}
    except Exception as exc:  # noqa: BLE001
        print(f"[render_e6] states fetch failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return {}


def _state(states, key):
    s = states.get(ENT[key])
    if not s:
        return None
    v = s.get("state")
    return None if v in (None, "unknown", "unavailable", "") else v


def _attr(states, key, attr):
    s = states.get(ENT[key])
    if not s:
        return None
    v = s.get("attributes", {}).get(attr)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _num(v, fmt="%.1f"):
    try:
        return fmt % float(v)
    except (TypeError, ValueError):
        return "--"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_news(limit=6):
    try:
        sys.path.insert(0, str(REPO / "scripts" / "the_daily"))
        import freshrss_bridge  # type: ignore
        items, _ = freshrss_bridge.fetch_top(limit=limit, pad=True)
        return items or []
    except Exception as exc:  # noqa: BLE001
        print(f"[render_e6] news unavailable ({type(exc).__name__}); skipping", file=sys.stderr)
        return []


def _ellipsize(font, text, max_w):
    if font.getlength(text) <= max_w:
        return text
    while text and font.getlength(text + "…") > max_w:
        text = text[:-1]
    return text + "…"


# ── E6 quantiser — mirrors esphome epaper_spi color_to_hex() exactly, then emits each
#    pixel in the requested palette (INK = pure source colours the device must receive;
#    PANEL_RGB = muted approximation of the real panel, for a faithful human preview).
def quantize(img: Image.Image, palette: dict) -> Image.Image:
    GRAY_THRESHOLD = 50
    px = img.load()
    out = Image.new("RGB", img.size)
    opx = out.load()
    cache: dict[tuple, tuple] = {}
    for y in range(img.height):
        for x in range(img.width):
            c = px[x, y]
            mapped = cache.get(c)
            if mapped is None:
                r, g, b = c[0], c[1], c[2]
                mx, mn = max(r, g, b), min(r, g, b)
                if (mx - mn) < GRAY_THRESHOLD:
                    bucket = "white" if (r + g + b) > 382 else "black"
                else:
                    r_on, g_on, b_on = r > 128, g > 128, b > 128
                    if r_on and g_on and not b_on:
                        bucket = "yellow"
                    elif r_on and not g_on and not b_on:
                        bucket = "red"
                    elif not r_on and g_on and not b_on:
                        bucket = "green"
                    elif not r_on and not g_on and b_on:
                        bucket = "blue"
                    elif not r_on and g_on and b_on:
                        bucket = "green"       # cyan → green
                    elif r_on and not g_on:
                        bucket = "red"         # magenta → red
                    elif r_on:
                        bucket = "white"
                    else:
                        bucket = "black"
                mapped = palette[bucket]
                cache[c] = mapped
            opx[x, y] = mapped
    return out


# ── Compose ────────────────────────────────────────────────────────────────────
def render(states, news) -> Image.Image:
    now = datetime.now()
    s = SS
    img = Image.new("RGB", (W * s, H * s), INK["white"])
    d = ImageDraw.Draw(img)

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
    NEWS = fnt(SANS, 15, 400)

    K, WHT, RED, GRN, BLU, YEL = (INK[c] for c in ("black", "white", "red", "green", "blue", "yellow"))

    def text(x, y, t, font, fill=K, anchor=None):
        d.text((x * s, y * s), t, font=font, fill=fill, anchor=anchor)

    def tw(t, font):
        return font.getlength(t) / s

    def fit_doto(t, max_w, sizes):
        for sz in sizes:
            f = doto(sz)
            if tw(t, f) <= max_w:
                return f, sz
        return doto(sizes[-1]), sizes[-1]

    def tile(x, y, w, h, r=16, outline=K, width=1, fill=None):
        d.rounded_rectangle([x * s, y * s, (x + w) * s, (y + h) * s], radius=int(r * s),
                            outline=outline, width=max(1, int(width * s)), fill=fill)

    def header(x, y, w, label, accent=K, fg=K):
        # small colour tab + mono label, top-left of a tile
        d.rounded_rectangle([x * s, (y + 1) * s, (x + 4) * s, (y + 13) * s], radius=int(2 * s), fill=accent)
        text(x + 12, y, label, LAB, fill=fg)

    def pill(x, y, w, h, t, font, fill=RED, fg=WHT):
        d.rounded_rectangle([x * s, y * s, (x + w) * s, (y + h) * s], radius=int(h / 2 * s), fill=fill)
        text(x + w / 2, y + h / 2, t, font, fill=fg, anchor="mm")

    def dotsicon(cx, cy, kind, R=18, col=K):
        def dt(px, py, rr=2.6):
            d.ellipse([(px - rr) * s, (py - rr) * s, (px + rr) * s, (py + rr) * s], fill=col)
        if kind == "sun":
            dt(cx, cy, 6)
            for a in range(0, 360, 45):
                dt(cx + math.cos(math.radians(a)) * R, cy + math.sin(math.radians(a)) * R, 2.4)
        elif kind == "moon":
            for a in range(40, 320, 28):
                dt(cx + math.cos(math.radians(a)) * R, cy + math.sin(math.radians(a)) * R, 2.6)
        elif kind in ("cloud", "snow"):
            for (px, py, rr) in [(cx - 9, cy + 2, 5), (cx + 1, cy - 4, 6.5), (cx + 11, cy + 2, 5),
                                 (cx - 3, cy + 4, 5), (cx + 7, cy + 4, 5)]:
                dt(px, py, rr)
        elif kind == "rain":
            for (px, py, rr) in [(cx - 8, cy - 3, 5), (cx + 2, cy - 7, 6), (cx + 10, cy - 3, 5)]:
                dt(px, py, rr)
            for px in (cx - 6, cx + 2, cx + 10):
                dt(px, cy + 8, 2.2, ); dt(px, cy + 14, 2.2)

    def ring(cx, cy, R, ratio, w=7, col=GRN, track=K):
        bb = [(cx - R) * s, (cy - R) * s, (cx + R) * s, (cy + R) * s]
        for a in range(0, 360, 12):  # faint dotted track
            d.ellipse([(cx + math.cos(math.radians(a)) * R - 1.2) * s,
                       (cy + math.sin(math.radians(a)) * R - 1.2) * s,
                       (cx + math.cos(math.radians(a)) * R + 1.2) * s,
                       (cy + math.sin(math.radians(a)) * R + 1.2) * s], fill=track)
        end = -90 + max(0.0, min(1.0, ratio)) * 360
        d.arc(bb, -90, end, fill=col, width=max(1, int(w * s)))

    GAP, M = 16, 20

    # ════════ TOP ROW ════════
    ty, th = 20, 206
    # CLOCK
    cx, cw = M, 326
    tile(cx, ty, cw, th, outline=K)
    header(cx + 20, ty + 18, cw, "NOW", accent=BLU)
    tstr = now.strftime("%H:%M")
    cf, _ = fit_doto(tstr, cw - 40, [112, 104, 96, 88])
    text(cx + cw / 2, ty + th / 2 + 6, tstr, cf, anchor="mm", fill=K)
    text(cx + 22, ty + th - 30, f"{now.year}-{now.month:02d}-{now.day:02d}", LAB, fill=K)
    wd = EN_WD[now.isoweekday() - 1]
    pw = tw(wd, LABB) + 24
    pill(cx + cw - 20 - pw, ty + th - 34, pw, 22, wd, LABB, fill=BLU)

    # WEATHER
    wx, ww = cx + cw + GAP, 196
    tile(wx, ty, ww, th, outline=K)
    header(wx + 20, ty + 18, ww, "WEATHER", accent=YEL)
    wstate = _state(states, "weather") or "cloudy"
    icon = WEATHER_ICON.get(wstate, "cloud")
    icol = YEL if icon in ("sun",) else (BLU if icon in ("rain", "snow") else K)
    dotsicon(wx + 46, ty + 74, icon, R=18, col=icol)
    wt = _num(_attr(states, "weather", "temperature"), "%.0f")
    wf, _ = fit_doto(f"{wt}°", ww - 40, [64, 56, 48])
    text(wx + 20, ty + 108, f"{wt}°", wf, fill=K)
    text(wx + 20, ty + th - 46, WEATHER_CN.get(wstate, "--"), CJKW, fill=BLU)

    # CALENDAR
    lx, lw = wx + ww + GAP, W - M - (wx + ww + GAP)
    tile(lx, ty, lw, th, outline=RED, fill=RED)                 # inverted: solid red card
    header(lx + 20, ty + 18, lw, EN_MON[now.month - 1], accent=WHT, fg=WHT)
    wd2 = EN_WD[now.isoweekday() - 1]
    text(lx + lw - 20, ty + 18, wd2, LABB, fill=WHT, anchor="ra")
    df, _ = fit_doto(f"{now.day:02d}", lw - 40, [120, 110, 100])
    text(lx + lw / 2, ty + th / 2 + 14, f"{now.day:02d}", df, anchor="mm", fill=WHT)

    # ════════ BOTTOM ROW ════════
    by, bh = ty + th + GAP, H - (ty + th + GAP) - M
    # HOME
    hx, hw = M, 248
    tile(hx, by, hw, bh, outline=K)
    header(hx + 20, by + 16, hw, "HOME", accent=GRN)
    temp = _num(_state(states, "temp"))
    hum = _num(_state(states, "humidity"), "%.0f")
    tv = _f(_state(states, "temp"))
    text(hx + 22, by + 46, "TEMP °C", LAB, fill=K)
    tf, _ = fit_doto(temp, 104, [44, 40, 36])
    text(hx + 22, by + 64, temp, tf, fill=(RED if (tv is not None and tv >= 28) else K))
    text(hx + 138, by + 46, "HUM %", LAB, fill=K)
    hf, _ = fit_doto(hum, 96, [44, 40, 36])
    text(hx + 138, by + 64, hum, hf, fill=BLU)
    # device status rows — green OK / red alert
    lb = _f(_state(states, "lock_batt")) or 0
    cat_full = states.get(ENT["cat_waste"], {}).get("state") == "on"
    cat_low = states.get(ENT["cat_sand"], {}).get("state") == "on"
    cat = ("FULL", RED) if cat_full else (("LOW", RED) if cat_low else ("OK", GRN))
    water = ("LOW", RED) if states.get(ENT["water_lack"], {}).get("state") == "on" else ("OK", GRN)
    batt_col = RED if lb < 20 else (K if lb < 50 else GRN)
    rows = [
        ("LOCK", f"{lb:.0f}%", batt_col),
        ("LITTER", cat[0], cat[1]),
        ("WATER", water[0], water[1]),
    ]
    ry = by + bh - 66
    for name, val, col in rows:
        text(hx + 22, ry, name, LAB, fill=K)
        text(hx + hw - 22, ry, val, LABB, fill=col, anchor="ra")
        ry += 20

    # AIR — inverted: the whole card fills with the air-quality level colour, reversed
    # to white ink, so overall air status reads at a glance (green good → red bad).
    ax, aw = hx + hw + GAP, 188
    pm = _f(_state(states, "pm25"))
    co = _f(_state(states, "co2"))
    hcho = _f(_state(states, "hcho"))
    hug = hcho * 1000 if hcho is not None else None   # mg/m³ → µg/m³
    # GB/T 18883 limit 0.08 mg/m³ = 80 µg/m³; green < 50, yellow 50-80, red > 80
    if hug is None:
        rcol = K
    elif hug > 80:
        rcol = RED
    elif hug >= 50:
        rcol = YEL
    else:
        rcol = GRN
    tile(ax, by, aw, bh, outline=rcol, fill=rcol)
    header(ax + 20, by + 16, aw, "AIR", accent=WHT, fg=WHT)
    ring(ax + aw / 2, by + 92, 52, (hug or 0) / 100, w=8, col=WHT, track=WHT)
    rtxt = _num(hug, "%.0f") + ("!" if (hug is not None and hug > 80) else "")
    rf, _ = fit_doto(rtxt, 84, [40, 34, 28])
    text(ax + aw / 2, by + 92, rtxt, rf, anchor="mm", fill=WHT)
    text(ax + aw / 2, by + 146, "甲醛 μg/m³", CJKS, anchor="ma", fill=WHT)
    text(ax + 20, by + bh - 46, "PM2.5", LAB, fill=WHT)
    text(ax + aw - 20, by + bh - 46, _num(pm, "%.0f"), LABB, fill=WHT, anchor="ra")
    text(ax + 20, by + bh - 24, "CO2", LAB, fill=WHT)
    text(ax + aw - 20, by + bh - 24, f"{_num(co, '%.0f')}", LABB, fill=WHT, anchor="ra")

    # NEWS (red bullets, black titles)
    nx = ax + aw + GAP
    nw = W - M - nx
    tile(nx, by, nw, bh, outline=K)
    header(nx + 20, by + 16, nw, "NEWS", accent=RED)
    ny = by + 46
    if not news:
        text(nx + 20, ny, "暂无新闻 / NO FEED", NEWS, fill=K)
    for it in news[:4]:
        if ny > by + bh - 30:
            break
        text(nx + 20, ny + 2, "●", CJKS, fill=RED)
        title = _ellipsize(NEWS, it.get("title") or "", (nw - 46) * s)
        text(nx + 36, ny, title, NEWS, fill=K)
        ny += 30

    return img.resize((W, H), Image.LANCZOS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT_PATH))
    ap.add_argument("--open", action="store_true", help="open the PNG after rendering (macOS)")
    ap.add_argument("--demo-news", action="store_true",
                    help="inject sample headlines for preview (production uses FreshRSS)")
    args = ap.parse_args()

    try:
        requests.packages.urllib3.disable_warnings()  # noqa: SLF001
    except Exception:
        pass

    states = fetch_states()
    news = fetch_news()
    if not news and args.demo_news:
        news = [
            {"title": "英伟达市值突破四万亿美元创历史新高"},
            {"title": "国常会:加大对科技创新企业金融支持"},
            {"title": "SpaceX 星舰第九次试飞成功回收"},
            {"title": "苹果 M5 芯片曝光,能效提升四成"},
        ]
    raw = render(states, news)

    out = Path(args.out)                       # DEVICE image: pure INK colours → panel
    out.parent.mkdir(parents=True, exist_ok=True)
    quantize(raw, INK).save(out)
    preview = out.with_name(out.stem + "_preview.png")   # muted, faithful human preview
    quantize(raw, PANEL_RGB).save(preview)
    print(f"[render_e6] device={out.name} preview={preview.name} "
          f"({out.stat().st_size}B)  states={len(states)} news={len(news)}")
    if args.open:
        os.system(f'open "{preview}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
