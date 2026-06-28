# E-ink Dashboard — HA as server, panel as client

Server-rendered dashboard for the **TRMNL 7.5" e-paper panel** (ESP32-S3 +
Waveshare 7.5" v2, 800×480 mono). HA renders a full image; the panel just
displays it. Same renderer (`render.py`) feeds **two mutually-exclusive panel
firmwares** — pick one:

| Path | Firmware | Transport | Sender | Trade-off |
|---|---|---|---|---|
| **A. WiFi pull** (active) | ESPHome `online_image` | WiFi HTTP | `deploy.py` (SCP PNG to HA) | no reflash, no range limit |
| **B. OpenDisplay push** | OpenDisplay | Bluetooth LE | `opendisplay_send.py` (py-opendisplay) | the stated goal; needs USB flash + BLE host near panel |

The device is currently on **Path A** (OTA-flashed, verified). Path B requires a
one-time USB reflash that *replaces* ESPHome — see "OpenDisplay firmware" below.

```
/root/ha box (cron)                  HA (192.168.50.154:8123)        TRMNL panel (192.168.50.135)
────────────────────                 ─────────────────────────       ───────────────────────────
scripts/eink/cycle.py ─┬─ render.py ─ states ─▶ /api/states
   (alternates)        │      │  ── FreshRSS ─▶ the_daily/freshrss_bridge
                       │      │  ── sprite ──── esphome/images/*.png
                       └─ photo.py ─── online photo (bing/picsum)
        ▼
   out/dashboard.png  ──── SCP ─────▶ /config/www/eink/dashboard.png
                                       (served at /local/eink/dashboard.png)
                                                   ▲
                                          ESPHome online_image GET every 10 min ┘
```

Why server-side rendering: arbitrary Chinese **news** text and **Pokémon**
sprites render trivially with Pillow, instead of pre-declaring every glyph
on-device (the old on-device lambda — git commit `be2cdc5`).

## Files

- `cycle.py` — **orchestrator the cron calls.** Strictly alternates dashboard ↔
  online photo frame each run (state in `out/.last_mode`), applies invert, writes
  `out/dashboard.png`. Falls back to the dashboard if the photo fetch fails.
- `render.py` — pulls HA state + FreshRSS news + a daily Pokémon sprite, composes
  an 800×480 **1-bit** PNG with Pillow (editorial serif/sans design). Standalone:
  missing sensors → `--`, FreshRSS/Pokémon failures degrade gracefully.
- `photo.py` — fetches an online photo, center-fits to 800×480, contrast-boosts and
  Floyd–Steinberg dithers to 1-bit. Source via `EINK_PHOTO_SOURCE`: `bing` (daily
  wallpaper, random of last 8 days; default) or `picsum` (random photo every fetch).
- `deploy.py` — pushes `out/dashboard.png` to HA `/config/www/eink/dashboard.png`.
  Uses `sshpass` if present (the box), else pure-python `paramiko` (dev machine).

## Content rotation

The panel always GETs one URL; `cycle.py` decides what that PNG is each run, so the
panel shows the dashboard on one refresh and a photo frame on the next. Tune via env:

- `EINK_INVERT=1` — pre-invert output (this panel maps the PNG inverted). Applies to
  both dashboard and photo (photo + panel invert cancel → normal, non-negative photo).
- `EINK_PHOTO_SOURCE=bing|picsum` — online photo provider.

The panel firmware lives in `esphome/trmnl_dashboard.yaml` (`http_request` +
`online_image` → `it.image()`).

## Run

```bash
cd /path/to/ha-config-as-code
set -a && source .env && set +a
.venv/bin/python scripts/eink/render.py     # → scripts/eink/out/dashboard.png
.venv/bin/python scripts/eink/deploy.py     # → HA /config/www/eink/dashboard.png
```

Preview the PNG locally by opening `scripts/eink/out/dashboard.png`.

**If the panel shows a black background** (ESPHome's `online_image` maps the PNG
inverted on this panel), render with `--invert` — or set `EINK_INVERT=1` in `.env`
so the cron picks it up too. The output PNG then has a black background, which the
panel flips back to white:

```bash
.venv/bin/python scripts/eink/render.py --invert
```

## Refresh loop (cron on the always-on box)

Mirror the_daily. Every 10 min, re-render + push; the panel pulls on its own
10-min `interval`, so worst-case staleness is ~0–20 min.

```cron
*/10 * * * * cd /root/ha && set -a && . ./.env && set +a && \
  /root/ha/.venv/bin/python /root/ha/scripts/eink/cycle.py && \
  /root/ha/.venv/bin/python /root/ha/scripts/eink/deploy.py \
  >> /var/log/eink.log 2>&1
```

Set `EINK_INVERT=1` (and optionally `EINK_PHOTO_SOURCE`) in `.env` so the cron picks
them up. To run the dashboard alone (no rotation), call `render.py` instead of `cycle.py`.

## Path A firmware — ESPHome (WiFi pull, currently active)

```bash
cd esphome
set -a && source ../.env && set +a
esphome run trmnl_dashboard.yaml --device 192.168.50.135   # OTA
```

The panel fetches `http://192.168.50.154:8123/local/eink/dashboard.png`. `/local/`
needs no auth, so the device requires no token.

## Path B firmware — OpenDisplay (BLE push, the stated goal)

OpenDisplay makes the panel a "dumb" receiver; a *sender* (this repo's
`opendisplay_send.py`, via py-opendisplay) renders + pushes the image over BLE.
The SDK is **BLE-only** — run the sender on a host with Bluetooth within ~10 m of
the panel. The HA host qualifies (its `bluetooth` integration is active).

**1. Flash OpenDisplay firmware (one-time, physical — only you can do this):**
   - Plug the panel into a computer via USB.
   - Open the **OpenDisplay Toolbox** in a Chromium-based browser (Chrome/Edge —
     Firefox lacks WebUSB/Web Bluetooth): <https://opendisplay.org/firmware/toolbox/>
   - Select the serial port; pick the **ESP32-S3 + Waveshare 7.5" (800×480 mono)**
     preset; flash. Optionally set BLE encryption (note the key) + deep-sleep.
   - This **overwrites the ESPHome firmware**. To revert, re-run the Path A OTA
     (the panel must be on WiFi; after deep-sleep flashing you may need USB).

**2. Discover the panel's BLE MAC and push:**
```bash
set -a && source .env && set +a
.venv/bin/python scripts/eink/opendisplay_send.py --discover      # prints name → MAC
export OPENDISPLAY_MAC=AA:BB:CC:DD:EE:FF                          # add to .env
# export OPENDISPLAY_KEY=<hex>   # only if you set BLE encryption in the Toolbox
.venv/bin/python scripts/eink/opendisplay_send.py                # render + push
```

**3. Refresh loop (cron on a Bluetooth-equipped always-on host near the panel):**
```cron
*/10 * * * * cd /root/ha && set -a && . ./.env && set +a && \
  /root/ha/.venv/bin/python /root/ha/scripts/eink/opendisplay_send.py \
  >> /var/log/eink.log 2>&1
```
No `deploy.py` / `/config/www` needed on Path B — the image is pushed directly.

## Layout

- **Left column**: clock, weather (MDI icon + 温度/湿度), 客厅温度/湿度 tiles,
  空气 (PM2.5/CO2) + status chips (门锁电量/猫厕所/饮水机).
- **Right column**: 新闻 (FreshRSS top headlines, source tag + age) and a
  daily Pokémon sprite in a reserved bottom band.

Entity IDs mirror `esphome/trmnl_dashboard.yaml` (pre-rewrite); edit `ENT` in
`render.py` to change sensors.

## Customizing

- **News**: FreshRSS via `the_daily/freshrss_bridge.fetch_top`. Off-box it
  returns `[]` and the column shows 暂无新闻.
- **Pokémon**: rotates daily through `esphome/images/*.png` (`POKEMON` list).
  Add a sprite + name to extend.
- **Output format**: 1-bit PNG (`mode "1"`). The panel reads it as
  `online_image type: BINARY`. If a panel mishandles 1-bit PNG, switch
  `render.py` to `mode "L"` and keep `type: BINARY` (luminance-thresholded).

## Failure modes

| What breaks | What you see |
|---|---|
| HA token missing/expired | tiles show `--`; render still succeeds |
| FreshRSS unreachable / off-box | 新闻 column shows 暂无新闻 |
| Sensor unavailable | that field shows `--` |
| Panel can't reach HA | `online_image` `on_error` logs; last image stays on screen |
| Sprite file missing | Pokémon band shows the name only |
