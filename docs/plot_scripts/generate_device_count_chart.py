#!/usr/bin/env python3
"""Generate an MD3-style horizontal bar chart (PNG) from live HA data.

Connects to the Home Assistant WebSocket API to fetch the device & entity
registries, classifies physical devices into categories, then renders a
PNG chart via cairosvg.

Requirements: pip install websockets cairosvg
Environment:  HA_URL, HA_TOKEN (loaded from .env)
"""

from __future__ import annotations

import asyncio
import base64
import collections
import json
import os
import subprocess
from pathlib import Path
import sys

# ---------------------------------------------------------------------------
# Font
# ---------------------------------------------------------------------------
FONT_PATHS = [
    Path("/root/ha/esphome/fonts/fusion-pixel-12px-proportional-zh_hans.ttf"),
]

# ---------------------------------------------------------------------------
# MD3 tonal palette — Purple seed #6750A4
# ---------------------------------------------------------------------------
TOKENS = {
    "primary": "#6750A4",
    "on_primary": "#FFFFFF",
    "primary_container": "#EADDFF",
    "on_primary_container": "#21005D",
    "secondary": "#625B71",
    "on_secondary": "#FFFFFF",
    "secondary_container": "#E8DEF8",
    "on_secondary_container": "#1D192B",
    "tertiary": "#7D5260",
    "tertiary_container": "#FFD8E4",
    "on_tertiary_container": "#31111D",
    "surface": "#FFFBFE",
    "on_surface": "#1C1B1F",
    "on_surface_variant": "#49454F",
    "surface_container_lowest": "#FFFFFF",
    "surface_container_low": "#F7F2FA",
    "surface_container": "#F3EDF7",
    "surface_container_high": "#ECE6F0",
    "surface_container_highest": "#E6E0E9",
    "outline": "#79747E",
    "outline_variant": "#CAC4D0",
}

# ---------------------------------------------------------------------------
# Layout constants (some are computed dynamically from row count)
# ---------------------------------------------------------------------------
WIDTH = 1600
CARD_X = 48
CARD_Y = 48
CARD_R = 28
BAR_H = 56
BAR_GAP = 28
BAR_R = 16

# Horizontal layout
PLOT_X = CARD_X + 380
PLOT_W = WIDTH - CARD_X * 2 - 480

# ---------------------------------------------------------------------------
# Localization
# ---------------------------------------------------------------------------
CATEGORY_EN = {
    "墙壁开关": "Wall Switches",
    "洗护家电": "Laundry Appliances",
    "空调/温控设备": "Climate / HVAC",
    "灯光设备": "Lighting",
    "窗帘/晾衣架": "Curtains / Airers",
    "风机/净化设备": "Fans / Purifiers",
    "清洁设备": "Cleaning",
    "媒体设备": "Media Players",
    "传感器/安防": "Sensors / Security",
    "智能设备": "Smart Devices",
}

TITLE_TEXT = {"zh": "家庭设备分类统计", "en": "Home Device Categories"}
CHIP_TEXT = {"zh": "共 {n} 台设备", "en": "{n} devices total"}

# ---------------------------------------------------------------------------
# Device classification (HA WebSocket)
# ---------------------------------------------------------------------------
# Manufacturers / models that are virtual (HACS, addons, integrations, …)
_SKIP_MANUFACTURERS = {
    "Browser Mod", "Home Assistant", "ESPHome",
    "Home Assistant Community Store", "Home Assistant Community Apps",
    "Official apps", "Music Assistant", "Balloob's experimental playground",
    "hacs.xyz",
}

# model values that indicate HACS frontend resources, not real devices
_VIRTUAL_MODEL_TYPES = {"integration", "plugin", "theme"}


def _is_virtual(dev: dict) -> bool:
    """Return True if this device registry entry is not a physical device."""
    mfr = dev.get("manufacturer") or ""
    model = dev.get("model") or ""
    name = dev.get("name_by_user") or dev.get("name") or ""
    if mfr in _SKIP_MANUFACTURERS:
        return True
    if model in ("Home Assistant App", "esp32-s3-devkitc-1"):
        return True
    if model in _VIRTUAL_MODEL_TYPES:
        return True
    if "Zigbee2MQTT" in mfr or "Zigbee2MQTT" in name:
        return True
    # Room-only entries (no manufacturer, no model, just area devices)
    if not mfr and not model:
        return True
    return False


def _classify(dev: dict, domains: set[str]) -> str | None:
    """Classify a physical device into a category. Returns None to skip."""
    model = dev.get("model") or ""
    name = dev.get("name_by_user") or dev.get("name") or ""

    # Wall switches (have light entities but ARE switches by model)
    if "xiaomi.switch." in model or "lumi.switch." in model:
        return "墙壁开关"

    # Smart controller / panel
    if "xiaomi.controller." in model:
        return "墙壁开关"

    # Washer / dryer / dishwasher
    washer_kw = ("washer", "wd74", "dv74", "sj65", "洗衣", "烘干", "洗碗")
    if any(k in model.lower() or k in name for k in washer_kw):
        return "洗护家电"

    # Climate (AC, thermostat, …) — but 浴霸 with climate goes to lights
    if "climate" in domains:
        if "bhf_light" in model:
            return "灯光设备"
        return "空调/温控设备"

    # Covers (curtains, airer)
    if "cover" in domains:
        return "窗帘/晾衣架"

    # Fans / air purifiers
    if "fan" in domains:
        return "风机/净化设备"

    # Vacuum / cleaning
    if "vacuum" in domains:
        return "清洁设备"

    # Media players (not Browser Mod — already filtered)
    if "media_player" in domains:
        return "媒体设备"

    # Lights (bulbs, strips, spotlights, 浴霸 without climate, …)
    if "light" in domains:
        return "灯光设备"

    # Sensors (motion, temperature, water leak, locks, …)
    if "sensor" in domains or "binary_sensor" in domains:
        return "传感器/安防"

    # Remaining switch-only (smart plugs, pet devices, etc.)
    if "switch" in domains:
        return "智能设备"

    return None


async def fetch_device_counts() -> list[tuple[str, int]]:
    """Connect to HA WebSocket and return [(category, count), …] sorted descending."""
    import websockets

    ha_url = os.environ["HA_URL"]
    token = os.environ["HA_TOKEN"]
    ws_url = ha_url.replace("http", "ws", 1) + "/api/websocket"

    async with websockets.connect(ws_url, max_size=10 * 1024 * 1024) as ws:
        await ws.recv()  # auth_required
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        await ws.recv()  # auth_ok

        await ws.send(json.dumps({"id": 1, "type": "config/device_registry/list"}))
        devices = json.loads(await ws.recv())["result"]

        await ws.send(json.dumps({"id": 2, "type": "config/entity_registry/list"}))
        entities = json.loads(await ws.recv())["result"]

    # device_id → set of entity domains
    dev_domains: dict[str, set[str]] = collections.defaultdict(set)
    for e in entities:
        did = e.get("device_id")
        if did:
            dev_domains[did].add(e["entity_id"].split(".")[0])

    cats: dict[str, int] = collections.Counter()
    for d in devices:
        if _is_virtual(d):
            continue
        domains = dev_domains.get(d["id"], set())
        cat = _classify(d, domains)
        if cat:
            cats[cat] += 1

    return sorted(cats.items(), key=lambda x: x[1], reverse=True)


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------
def _find_font() -> tuple[Path | None, str]:
    """Return (font_path, fontconfig_family_name) or (None, "")."""
    for p in FONT_PATHS:
        if p.exists():
            r = subprocess.run(
                ["fc-query", "--format", "%{family}", str(p)],
                capture_output=True, text=True,
            )
            family = r.stdout.strip() if r.returncode == 0 else ""
            return p, family
    return None, ""


def _font_base64(font_path: Path) -> str:
    return base64.b64encode(font_path.read_bytes()).decode()


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


# ---------------------------------------------------------------------------
# SVG rendering
# ---------------------------------------------------------------------------
def _md3_elevation_shadow(eid: str, level: int = 1) -> str:
    if level == 1:
        return (
            f'<filter id="{eid}" x="-8%" y="-8%" width="116%" height="124%">'
            f'<feDropShadow dx="0" dy="1" stdDeviation="3" flood-color="#000" flood-opacity="0.15"/>'
            f'<feDropShadow dx="0" dy="1" stdDeviation="2" flood-color="#000" flood-opacity="0.30"/>'
            f'</filter>'
        )
    return (
        f'<filter id="{eid}" x="-8%" y="-8%" width="116%" height="124%">'
        f'<feDropShadow dx="0" dy="2" stdDeviation="6" flood-color="#000" flood-opacity="0.15"/>'
        f'<feDropShadow dx="0" dy="1" stdDeviation="2" flood-color="#000" flood-opacity="0.30"/>'
        f'</filter>'
    )


def _bar_colors(index: int) -> tuple[str, str, str, str]:
    palette = [
        (TOKENS["primary"], TOKENS["primary_container"], TOKENS["on_primary_container"]),
        (TOKENS["secondary"], TOKENS["secondary_container"], TOKENS["on_secondary_container"]),
        (TOKENS["tertiary"], TOKENS["tertiary_container"], TOKENS["on_tertiary_container"]),
    ]
    fill, badge_bg, badge_fg = palette[index % len(palette)]
    track = TOKENS["surface_container_highest"]
    return fill, badge_bg, badge_fg, track


def build_svg(data: list[tuple[str, int]], font_path: Path | None, fc_family: str = "", lang: str = "zh") -> tuple[str, int, int]:
    """Build the SVG string. Returns (svg_content, width, height)."""
    n_rows = len(data)
    header_h = 160
    footer_h = 80
    plot_h = n_rows * (BAR_H + BAR_GAP) - BAR_GAP
    card_h = header_h + plot_h + footer_h + 60
    height = card_h + CARD_Y * 2
    card_w = WIDTH - CARD_X * 2
    plot_y = CARD_Y + header_h + 30

    max_v = max(v for _, v in data)

    s: list[str] = []
    add = s.append
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}">')

    # --- defs ---
    add("<defs>")
    add(_md3_elevation_shadow("elev1", 1))

    font_css = ""
    if font_path:
        b64 = _font_base64(font_path)
        font_css = (
            "@font-face {\n"
            "  font-family: 'ChartFont';\n"
            f"  src: url('data:font/truetype;base64,{b64}') format('truetype');\n"
            "}\n"
        )

    families = []
    if fc_family:
        families.append(f"'{fc_family}'")
    families.append("'ChartFont'")
    families.extend(["'Noto Sans SC'", "'Roboto'", "system-ui", "sans-serif"])
    font_family_css = ", ".join(families)

    add("<style><![CDATA[\n"
        f"{font_css}"
        "text {\n"
        f"  font-family: {font_family_css};\n"
        "}\n"
        "]]></style>")
    add("</defs>")

    # --- background ---
    add(f'<rect width="100%" height="100%" fill="{TOKENS["surface"]}"/>')

    # --- card ---
    add(f'<rect x="{CARD_X}" y="{CARD_Y}" width="{card_w}" height="{card_h}" '
        f'rx="{CARD_R}" fill="{TOKENS["surface_container_lowest"]}" filter="url(#elev1)"/>')
    add(f'<rect x="{CARD_X}" y="{CARD_Y}" width="{card_w}" height="{card_h}" '
        f'rx="{CARD_R}" fill="none" stroke="{TOKENS["outline_variant"]}" stroke-width="1"/>')

    # --- header ---
    hx = CARD_X + 48
    add(f'<text x="{hx}" y="{CARD_Y + 76}" font-size="48" font-weight="700" '
        f'fill="{TOKENS["on_surface"]}">{_esc(TITLE_TEXT[lang])}</text>')

    # divider
    dy = CARD_Y + 112
    add(f'<line x1="{hx}" y1="{dy}" x2="{CARD_X + card_w - 48}" y2="{dy}" '
        f'stroke="{TOKENS["outline_variant"]}" stroke-width="1"/>')

    # --- grid guides ---
    y_end = plot_y + plot_h
    step = 10
    for t in range(0, max_v + 1, step):
        x = PLOT_X + (t / max_v) * PLOT_W
        add(f'<line x1="{x:.1f}" y1="{plot_y - 12}" x2="{x:.1f}" y2="{y_end + 12}" '
            f'stroke="{TOKENS["outline_variant"]}" stroke-width="1" stroke-dasharray="4 4" '
            f'opacity="0.6"/>')
        add(f'<text x="{x:.1f}" y="{y_end + 44}" text-anchor="middle" font-size="18" '
            f'font-weight="500" fill="{TOKENS["on_surface_variant"]}">{t}</text>')

    # --- bars ---
    for i, (name, val) in enumerate(data):
        y = plot_y + i * (BAR_H + BAR_GAP)
        w = (val / max_v) * PLOT_W
        fill, badge_bg, badge_fg, track = _bar_colors(i)

        label = name if lang == "zh" else CATEGORY_EN.get(name, name)
        add(f'<text x="{PLOT_X - 20}" y="{y + BAR_H / 2 + 8:.1f}" text-anchor="end" '
            f'font-size="28" font-weight="600" fill="{TOKENS["on_surface"]}">{_esc(label)}</text>')

        add(f'<rect x="{PLOT_X}" y="{y}" width="{PLOT_W:.1f}" height="{BAR_H}" '
            f'rx="{BAR_R}" fill="{track}"/>')

        if w > 0:
            add(f'<rect x="{PLOT_X}" y="{y}" width="{w:.1f}" height="{BAR_H}" '
                f'rx="{BAR_R}" fill="{fill}"/>')

        bw = 64
        bh = 36
        bx = PLOT_X + w + 14
        by = y + (BAR_H - bh) / 2
        if bx + bw > PLOT_X + PLOT_W + 80:
            bx = PLOT_X + w - bw - 14
            badge_bg = "rgba(255,255,255,0.85)"
            badge_fg = fill

        add(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw}" height="{bh}" '
            f'rx="18" fill="{badge_bg}" filter="url(#elev1)"/>')
        add(f'<text x="{bx + bw / 2:.1f}" y="{by + bh / 2 + 7:.1f}" text-anchor="middle" '
            f'font-size="22" font-weight="700" fill="{badge_fg}">{val}</text>')

    # --- total chip ---
    total = sum(v for _, v in data)
    chip_text = CHIP_TEXT[lang].format(n=total)
    chip_w = 240 if lang == "en" else 200
    chip_h = 44
    chip_x = CARD_X + card_w - 48 - chip_w
    chip_y = CARD_Y + card_h - 64
    add(f'<rect x="{chip_x}" y="{chip_y}" width="{chip_w}" height="{chip_h}" '
        f'rx="22" fill="{TOKENS["primary_container"]}"/>')
    add(f'<text x="{chip_x + chip_w / 2}" y="{chip_y + chip_h / 2 + 8}" text-anchor="middle" '
        f'font-size="24" font-weight="600" fill="{TOKENS["on_primary_container"]}">{chip_text}</text>')

    add("</svg>")
    return "\n".join(s), WIDTH, height


# ---------------------------------------------------------------------------
# PNG export
# ---------------------------------------------------------------------------
def export_png(svg_path: Path, png_path: Path, font_path: Path | None, w: int, h: int) -> None:
    try:
        import cairosvg
    except ImportError:
        print("PNG export skipped: cairosvg not installed (uv pip install cairosvg)")
        return

    if font_path:
        fc_dir = Path.home() / ".local" / "share" / "fonts"
        fc_dir.mkdir(parents=True, exist_ok=True)
        dest = fc_dir / font_path.name
        if not dest.exists():
            import shutil
            shutil.copy2(font_path, dest)
            subprocess.run(["fc-cache", "-f"], capture_output=True)
            print(f"Installed font to {dest}")

    cairosvg.svg2png(
        url=str(svg_path.resolve()),
        write_to=str(png_path),
        output_width=w * 2,
        output_height=h * 2,
    )
    print(f"Generated: {png_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    outputs = [
        ("zh", Path("docs/device_category_counts_md3.png")),
        ("en", Path("docs/device_category_counts_md3_en.png")),
    ]

    # Fetch live data from HA
    print("Fetching device data from Home Assistant...")
    try:
        data = asyncio.run(fetch_device_counts())
    except Exception as exc:
        print(f"Failed to fetch HA data: {exc}")
        return 1

    for cat, count in data:
        print(f"  {cat:16s} {count}")

    font_path, fc_family = _find_font()
    if font_path:
        print(f"Using font: {font_path.name} (fc: {fc_family})")

    for lang, png_path in outputs:
        print(f"Generating PNG ({lang})...")
        svg_content, w, h = build_svg(data, font_path, fc_family, lang=lang)

        tmp_svg = png_path.with_suffix(".tmp.svg")
        tmp_svg.write_text(svg_content, encoding="utf-8")
        try:
            export_png(tmp_svg, png_path, font_path, w, h)
        except Exception as exc:
            print(f"PNG export failed ({lang}): {exc}")
            return 1
        finally:
            tmp_svg.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
