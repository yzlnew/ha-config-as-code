# Home Assistant Configuration as Code

中文版: [README.md](README.md)

Manage Home Assistant automations, scenes, dashboard, and device settings as code using Python scripts plus HA REST/WebSocket APIs.

## Highlights

- API-first workflow via `/api/*` and `/api/websocket`
- Idempotent scripts (safe to re-run in most cases)
- Git-friendly change tracking and rollback
- Layered deployment model (switches/scenes/automations/groups/dashboard/integrations)

## Current Repository Layout

```text
ha/
├── README.md
├── README.en.md
├── TODO.md
├── .env.example
├── docs/
│   ├── blog-post-by-human.md
│   ├── blog-post.md
│   ├── ha-unicode-bug-report.md
│   ├── ha_family_manual_md3.html
│   └── matter-thread-offline-fix.md
├── esphome/
│   ├── trmnl_dashboard.yaml
│   ├── fonts/
│   └── images/
├── scripts/
│   ├── ha_api.py
│   ├── setup_wireless_switches.py
│   ├── setup_scenes.py
│   ├── setup_automations.py
│   ├── create_groups.py
│   ├── setup_dashboard.py
│   ├── setup_adaptive_lighting.py
│   ├── setup_homekit.py
│   ├── setup_power_on_state.py
│   ├── setup_weather_forecast.py
│   └── utils/
│       ├── ha_update_pokemon.py
│       ├── list_scenes.py
│       └── find_lock_entity.py
└── .claude/
    └── skills/
        └── interface-design/
```

## Environment Variables

Copy and edit:

```bash
cp .env.example .env
```

Variables:

```env
HA_URL=http://YOUR_HA_IP:8123
HA_EXTERNAL_URL=https://your-domain.com:PORT
HA_TOKEN=your_long_lived_access_token
HA_SSH_HOST=YOUR_HA_IP
HA_SSH_USER=hassio
HA_SSH_PASSWORD=your_password
```

Notes:

- `scripts/ha_api.py` uses `HA_EXTERNAL_URL` first, then falls back to `HA_URL`
- `setup_weather_forecast.py` needs SSH vars to write HA config files

## Dependencies

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install requests websocket-client urllib3 python-dotenv
```

Extra requirement (only for `setup_weather_forecast.py`):

- `sshpass` installed on the machine running scripts
- SSH + sudo access to `/homeassistant` on HA host

## Required Integrations & Plugins

### HACS Integrations

- [Adaptive Lighting](https://github.com/basnijholt/adaptive-lighting): per-area adaptive color temperature and brightness curves, replacing vendor-native circadian lighting

### HACS Frontend Cards

- [Mushroom](https://github.com/piitaya/lovelace-mushroom): primary card components for the dashboard
- [button-card](https://github.com/custom-cards/button-card): custom button styling
- [card-mod](https://github.com/thomasloven/lovelace-card-mod): shadow DOM CSS injection for deep styling of Mushroom and other cards

### Official / Core Integrations

- [Matter](https://www.home-assistant.io/integrations/matter/): Matter light device support
- [HomeKit Bridge](https://www.home-assistant.io/integrations/homekit/): expose non-Matter devices to Apple Home
- [Xiaomi Miot Auto](https://github.com/al-one/hass-xiaomi-miot): Xiaomi/Mi Home device support (lights, switches, sensors, bathroom heaters, etc.)
- [ESPHome](https://www.home-assistant.io/integrations/esphome/): ESP-based devices such as the e-ink display

## Recommended Execution Order

```bash
# 1) Put wall switches into wireless mode (first-time setup)
.venv/bin/python scripts/setup_wireless_switches.py --set-wireless

# 2) Remove legacy automations and bind event automations
.venv/bin/python scripts/setup_wireless_switches.py --cleanup --bind

# 3) Scenes
.venv/bin/python scripts/setup_scenes.py

# 4) Automations + helpers
.venv/bin/python scripts/setup_automations.py

# 5) Light groups
.venv/bin/python scripts/create_groups.py

# 6) Dashboard (optional theme)
.venv/bin/python scripts/setup_dashboard.py --theme md3_yellow

# 7) Adaptive Lighting
.venv/bin/python scripts/setup_adaptive_lighting.py

# 8) HomeKit Bridge
.venv/bin/python scripts/setup_homekit.py

# 9) Power-on behavior
.venv/bin/python scripts/setup_power_on_state.py

# 10) Forecast template sensors (for ESPHome and other consumers)
.venv/bin/python scripts/setup_weather_forecast.py
```

## Script Overview

### Core API

- `scripts/ha_api.py`: shared REST client, auth, and helper methods for upserting automations/scenes

### Configuration Scripts

- `scripts/setup_wireless_switches.py`
  - `--set-wireless`: set all switch buttons to wireless mode
  - `--cleanup`: remove old on/off automations
  - `--bind`: create event-based button automations and set entity display metadata
- `scripts/setup_scenes.py`: creates Guest/Cinema/Sleep scenes, reloads scenes, applies Chinese display names/icons
- `scripts/setup_automations.py`: deploys environment/safety/presence/pet/leave-home automations and ensures helper entities
- `scripts/create_groups.py`: creates area light groups and whole-home strip groups
- `scripts/setup_dashboard.py`: generates and writes Lovelace dashboard via WebSocket
- `scripts/setup_adaptive_lighting.py`: creates per-area Adaptive Lighting entries
- `scripts/setup_homekit.py`: configures HomeKit Bridge while excluding Matter-direct devices
- `scripts/setup_power_on_state.py`: auto-discovers power-on select entities and sets memory/previous mode
- `scripts/setup_weather_forecast.py`: writes template sensor YAML and reloads templates for multi-day forecast data

### Utility Scripts

- `scripts/utils/ha_update_pokemon.py`: daily Pokemon updater (intended for HA container shell_command)
- `scripts/utils/list_scenes.py`: prints all `scene.*` entities
- `scripts/utils/find_lock_entity.py`: searches lock-related entities by keywords

## Dashboard Themes

Supported in `setup_dashboard.py`:

- `md3_yellow` (default)
- `apple_home`
- `tech_scifi`
- `minimal_dark`
- `warm_cabin`

Example:

```bash
.venv/bin/python scripts/setup_dashboard.py --theme apple_home
```

## ESPHome

- `esphome/trmnl_dashboard.yaml`: TRMNL (ESP32-S3) status display config
- Depends on HA forecast template sensors created by `setup_weather_forecast.py`
- Font and pixel assets are under `esphome/fonts/` and `esphome/images/`

## Notes

- This is a real-home, entity-specific codebase; IDs are environment-dependent
- For migration, update entity mapping constants in each script first
- Commit before/after major runs to keep diffs and rollback clean
