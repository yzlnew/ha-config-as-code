"""Fetchers for each dashboard section. Each returns a JSON-serializable dict.
On HA errors a fetcher returns a degraded-but-valid shape (nulls / empty lists),
never raises (compose.py decides overall exit code)."""

from __future__ import annotations

import os as _os
import re
import sys
import sys as _sys
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

_HERE = _os.path.dirname(_os.path.abspath(__file__))
_SCRIPTS = _os.path.dirname(_HERE)
for _p in (_HERE, _SCRIPTS):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import _bootstrap  # noqa: F401
from _ws import WSClient

import ha_api  # type: ignore


# ---- HA REST helpers ----------------------------------------------------

def _states() -> list[dict]:
    return ha_api.api("GET", "/api/states")


def _by_id(states: Iterable[dict]) -> dict[str, dict]:
    return {s["entity_id"]: s for s in states}


def _state(entity_id: str, states: dict[str, dict]) -> dict | None:
    return states.get(entity_id)


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "" or value in ("unavailable", "unknown"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _attr(entity: dict | None, key: str) -> Any:
    if not entity:
        return None
    return (entity.get("attributes") or {}).get(key)


def _short_room(name: str) -> str | None:
    rooms = ["客厅", "主卧", "次卧", "书房", "西厨", "玄关", "卫生间", "主卫", "次卫", "阳台", "餐厅", "走廊", "厨房"]
    for r in rooms:
        if r in name:
            return r
    return None


# ---- Edition number (whimsy: days-since-Jan-1 + roman volume) -----------

def edition_string(now: datetime) -> str:
    year = now.year
    day_of_year = now.timetuple().tm_yday
    volume = year - 2024  # arbitrary epoch — yields III for 2026
    roman = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII"}.get(volume, str(volume))
    return f"Vol. {roman} · No. {day_of_year} · {year}"


# ---- Weather + sun ------------------------------------------------------

WEATHER_TRANSLATE = {
    "sunny": "晴", "clear-night": "晴夜",
    "cloudy": "多云", "partlycloudy": "晴转多云",
    "rainy": "雨", "pouring": "大雨",
    "snowy": "雪", "snowy-rainy": "雨雪",
    "fog": "雾", "windy": "风", "windy-variant": "风",
    "hail": "冰雹", "lightning": "雷电", "lightning-rainy": "雷雨",
    "exceptional": "特殊天气",
}


def fetch_lead(states_dict: dict[str, dict]) -> dict:
    now = datetime.now()
    weather = _state("weather.forecast_wo_de_jia", states_dict)
    cond = (weather or {}).get("state")
    cond_zh = WEATHER_TRANSLATE.get(cond, cond or "—")
    temp = _num(_attr(weather, "temperature"))
    weekday = now.strftime("%A")
    month_day = now.strftime("%B %-d")
    parts = [f"{weekday}, {month_day}", "上海"]
    if temp is not None:
        parts.append(f"{cond_zh} {temp:.0f}°")
    else:
        parts.append(cond_zh)

    # sunset
    sun = _state("sun.sun", states_dict)
    next_setting = _attr(sun, "next_setting")
    sunset_str = "—"
    if next_setting:
        try:
            dt = datetime.fromisoformat(next_setting.replace("Z", "+00:00"))
            sunset_str = dt.astimezone().strftime("%H:%M")
        except Exception:
            pass

    return {
        "lead": " · ".join(parts),
        "stamp_suffix": f" · sunset {sunset_str}",
    }


# ---- Today prose --------------------------------------------------------

def _time_phrase(hour: int) -> str:
    if 5 <= hour < 10: return "Quiet morning"
    if 10 <= hour < 12: return "A calm forenoon"
    if 12 <= hour < 14: return "Midday lull"
    if 14 <= hour < 17: return "A still afternoon"
    if 17 <= hour < 20: return "Easy evening"
    if 20 <= hour < 24: return "Late hours"
    return "Deep night"


def _light_phrase(n: int) -> str:
    if n == 0: return "All lights are off."
    if n == 1: return f'<b class="num">1</b> light still on.'
    if n <= 4: return f'<b class="num">{n}</b> lights still on.'
    if n <= 10: return f'<b class="num">{n}</b> lights on around the home.'
    return f'<b class="num">{n}</b> lights on — the place is busy.'


def fetch_today_prose(house: dict, climate: dict, air: dict) -> str:
    hour = datetime.now().hour
    parts = [_time_phrase(hour) + "."]

    # Living room temp + indoor humidity inline
    living_temp = climate.get("living_temp")
    indoor_hum = air.get("humidity")
    pm = air.get("pm25")

    inline_bits: list[str] = []
    if living_temp is not None:
        inline_bits.append(f'Living room <b class="num">{living_temp:.1f}°</b>')
    if indoor_hum is not None:
        inline_bits.append(f'humidity <b class="num">{int(indoor_hum)}%</b>')
    if pm is not None:
        inline_bits.append(f'PM2.5 <b class="num">{int(pm)}</b>')
    if inline_bits:
        parts.append(", ".join(inline_bits) + ".")

    parts.append(_light_phrase(house.get("lights_on") or 0))

    return " ".join(parts)


# ---- House tile ---------------------------------------------------------

def fetch_house(states_list: list[dict]) -> dict:
    lights = [s for s in states_list if s["entity_id"].startswith("light.")]
    on = [s for s in lights if s.get("state") == "on"]

    # Bucket by room (substring match on friendly_name)
    buckets: dict[str, list[dict]] = {}
    for s in lights:
        name = _attr(s, "friendly_name") or ""
        room = _short_room(name)
        if not room:
            continue
        buckets.setdefault(room, []).append(s)

    rows: list[dict] = []
    for room, group in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        room_on = sum(1 for x in group if x.get("state") == "on")
        kind = "ok" if room_on else "dim"
        rows.append(
            {
                "k": room,
                "v": f"{room_on}/{len(group)} on",
                "kind": kind if room_on else None,
            }
        )
        if len(rows) >= 5:
            break

    return {
        "value": len(on),
        "subscript": "on",
        "meta": f"{len(lights)} lights",
        "meter_on": len(on),
        "meter_total": min(20, max(8, len(lights) // 8)),
        "rows": rows or [{"k": "—", "v": "no lights detected", "kind": "dim"}],
        "lights_on": len(on),
        "lights_total": len(lights),
    }


# ---- Climate tile -------------------------------------------------------

CLIMATE_PRIORITY = [
    ("climate.lemesh_cn_2000792394_air02", "客厅"),
    ("climate.lemesh_cn_2000792363_air02", "主卧"),
    ("climate.lemesh_cn_2000792347_air02", "书房"),
    ("climate.lemesh_cn_2000792396_air02", "次卧"),
    ("climate.lemesh_cn_2000792371_air02", "西厨"),
    ("climate.lemesh_cn_2000794495_air02", "背景"),
]


def fetch_climate(states_dict: dict[str, dict]) -> dict:
    rows: list[dict] = []
    living_temp: float | None = None
    on_count = 0
    for ent_id, label in CLIMATE_PRIORITY:
        ent = _state(ent_id, states_dict)
        if not ent:
            continue
        state = ent.get("state")
        cur = _num(_attr(ent, "current_temperature"))
        target = _num(_attr(ent, "temperature"))
        is_off = state in ("off", None, "unavailable")
        if not is_off:
            on_count += 1
        # Track 客厅 temperature; if AC reports None (off), fall back later.
        if label == "客厅" and cur is not None and living_temp is None:
            living_temp = cur

    # If no climate entity gave a current temperature, fall back to the
    # whole-home air-quality sensor (xiaomi 米家全效空气净化器 in living area).
    if living_temp is None:
        air_temp = _state(AIR_PRIMARY_TEMP, states_dict)
        if air_temp:
            living_temp = _num(air_temp.get("state"))

    # Re-iterate to build rows AFTER fallback resolved (need to put loop order right).
    rows = []
    for ent_id, label in CLIMATE_PRIORITY:
        ent = _state(ent_id, states_dict)
        if not ent:
            continue
        state = ent.get("state")
        cur = _num(_attr(ent, "current_temperature"))
        target = _num(_attr(ent, "temperature"))
        is_off = state in ("off", None, "unavailable")

        if is_off:
            v = f"off · {cur:.1f}°" if cur is not None else "off"
            kind = "dim"
        else:
            v_parts = [state]
            if target is not None:
                v_parts.append(f"→{target:.0f}°")
            if cur is not None:
                v_parts.append(f"now {cur:.1f}°")
            v = " ".join(v_parts)
            kind = "ok"

        rows.append({"k": label + " 空调", "v": v, "kind": kind})

    living_v = f"{living_temp:.1f}°" if living_temp is not None else "—"
    cap = f"{on_count}/{len(rows)} units active." if rows else "Climate data unavailable."

    return {
        "value": living_v,
        "subscript": "客厅",
        "meta": f"{len(rows)} zones",
        "caption": cap,
        "rows": rows[:5],
        "living_temp": living_temp,
    }


# ---- Air Quality tile ---------------------------------------------------

AIR_PRIMARY_PM25 = "sensor.xiaomi_cn_2008215373_ua3a_pm2_5_density_p_3_4"
AIR_PRIMARY_TEMP = "sensor.xiaomi_cn_2008215373_ua3a_temperature_p_3_7"
AIR_PRIMARY_HUM = "sensor.xiaomi_cn_2008215373_ua3a_relative_humidity_p_3_1"
AIR_SECONDARY_PM25 = "sensor.dmaker_cn_457366768_f20_pm2_5_density_p_3_4"


def _pm_band(pm: float) -> tuple[str, str]:
    if pm < 35: return "good", "ok"
    if pm < 75: return "moderate", "dim"
    if pm < 150: return "unhealthy", "warn"
    return "hazardous", "warn"


def fetch_air(states_dict: dict[str, dict]) -> dict:
    pm = _num(_state(AIR_PRIMARY_PM25, states_dict).get("state") if _state(AIR_PRIMARY_PM25, states_dict) else None)
    temp = _num(_state(AIR_PRIMARY_TEMP, states_dict).get("state") if _state(AIR_PRIMARY_TEMP, states_dict) else None)
    hum = _num(_state(AIR_PRIMARY_HUM, states_dict).get("state") if _state(AIR_PRIMARY_HUM, states_dict) else None)
    pm2 = _num(_state(AIR_SECONDARY_PM25, states_dict).get("state") if _state(AIR_SECONDARY_PM25, states_dict) else None)

    rows: list[dict] = []
    if temp is not None:
        rows.append({"k": "温度", "v": f"{temp:.1f}°", "kind": None})
    if hum is not None:
        rows.append({"k": "湿度", "v": f"{int(hum)}%", "kind": None})
    if pm is not None:
        band, kind = _pm_band(pm)
        rows.append({"k": "PM2.5 主", "v": f"{int(pm)} µg/m³", "kind": kind})
    if pm2 is not None:
        band2, kind2 = _pm_band(pm2)
        rows.append({"k": "PM2.5 次", "v": f"{int(pm2)} µg/m³", "kind": kind2})

    if pm is not None:
        band, _ = _pm_band(pm)
        cap = f"Indoor air {band}."
        if pm2 is not None:
            cap += f" Secondary {int(pm2)}."
    else:
        cap = "Air sensors offline."

    return {
        "value": int(pm) if pm is not None else None,
        "subscript": "PM2.5",
        "meta": "main + 2nd",
        "caption": cap,
        "rows": rows or [{"k": "—", "v": "no readings", "kind": "dim"}],
        "pm25": pm,
        "humidity": hum,
        "temperature": temp,
    }


# ---- Energy tile (best-effort) -----------------------------------------

ENERGY_CANDIDATES = [
    "sensor.energy_today",
    "sensor.daily_energy",
    "sensor.total_daily_energy",
    "sensor.home_daily_energy",
    "sensor.electricity_today",
]


def fetch_energy(states_dict: dict[str, dict]) -> dict:
    # Try candidates first
    value: float | None = None
    chosen: str | None = None
    for cand in ENERGY_CANDIDATES:
        ent = _state(cand, states_dict)
        if ent:
            n = _num(ent.get("state"))
            if n is not None:
                value = n
                chosen = cand
                break

    # Fallback: sum any *_energy sensors with unit kWh and a daily-looking name
    if value is None:
        total = 0.0
        hits = 0
        for ent_id, ent in states_dict.items():
            if not ent_id.startswith("sensor."):
                continue
            unit = _attr(ent, "unit_of_measurement")
            if unit != "kWh":
                continue
            cls = _attr(ent, "device_class") or ""
            sc = _attr(ent, "state_class") or ""
            # Want "total_increasing"-ish daily sensors only, but state_class doesn't clearly mark daily
            # so we just sum kWh sensors that look like power_consumption_today / daily
            if not re.search(r"(today|daily|day)", ent_id):
                continue
            n = _num(ent.get("state"))
            if n is not None:
                total += n
                hits += 1
        if hits > 0:
            value = total
            chosen = f"sum of {hits} *daily* kWh sensors"

    rows = [
        {"k": "晨间 06:30", "v": "ready", "kind": "dim"},
        {"k": "归家 灯光", "v": "armed", "kind": "dim"},
        {"k": "夜安 22:30", "v": "armed", "kind": "dim"},
    ]
    if chosen:
        rows.append({"k": "源", "v": chosen[:24], "kind": "dim"})

    return {
        "value": f"{value:.2f}" if value is not None else None,
        "subscript": "kWh",
        "meta": "today",
        "bars": [],  # MVP: empty → frontend renders neutral placeholder bars
        "rows": rows,
    }


# ---- Calendar -----------------------------------------------------------

CAL_PRIMARY = "calendar.yzlnew_gmail_com"
CAL_HOLIDAYS = "calendar.zhong_guo_jie_jia_ri"
CAL_BIRTHDAYS = "calendar.birthdays"


def _fetch_one_calendar(entity_id: str, start: datetime, end: datetime) -> list[dict]:
    # HA expects UTC ISO with Z suffix; '+' in offsets gets URL-mangled to space.
    iso_start = start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    iso_end = end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path = f"/api/calendars/{entity_id}?start={iso_start}&end={iso_end}"
    try:
        return ha_api.api("GET", path)
    except Exception as e:
        print(f"[calendar] {entity_id}: {e}", file=sys.stderr)
        return []


def fetch_calendar() -> dict:
    now = datetime.now().astimezone()
    end = now + timedelta(hours=24)

    primary = _fetch_one_calendar(CAL_PRIMARY, now, end)
    holidays = _fetch_one_calendar(CAL_HOLIDAYS, now, end)
    birthdays = _fetch_one_calendar(CAL_BIRTHDAYS, now, end)

    events: list[dict] = []

    # Build rows with source pill
    for ev in primary:
        events.append({**ev, "_src": "primary"})
    for ev in holidays:
        events.append({**ev, "_src": "holiday"})
    for ev in birthdays:
        events.append({**ev, "_src": "birthday"})

    # Sort by start time (handle all-day events)
    def _start_dt(ev: dict) -> datetime:
        s = ev.get("start", {})
        if isinstance(s, dict):
            v = s.get("dateTime") or s.get("date")
        else:
            v = s
        if not v:
            return datetime.max.replace(tzinfo=timezone.utc)
        try:
            if "T" in v:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            return datetime.fromisoformat(v + "T00:00:00").astimezone()
        except Exception:
            return datetime.max.replace(tzinfo=timezone.utc)

    events.sort(key=_start_dt)
    events = events[:5]

    out_events: list[dict] = []
    for ev in events:
        s = ev.get("start", {})
        e = ev.get("end", {})
        all_day = isinstance(s, dict) and "date" in s and "dateTime" not in s
        title = ev.get("summary") or ev.get("title") or "(no title)"
        location = ev.get("location") or ev.get("description") or ""
        # truncate description noise
        if location:
            location = re.sub(r"\s+", " ", location).strip()[:60]

        if all_day:
            time_str = "all-day"
            duration = "today"
        else:
            try:
                start_dt = _start_dt(ev)
                end_dt = _start_dt({"start": e}) if e else None
                time_str = start_dt.astimezone().strftime("%H:%M")
                if end_dt:
                    delta = end_dt - start_dt
                    mins = int(delta.total_seconds() // 60)
                    duration = f"{mins} min" if mins < 60 else f"{mins // 60} h"
                else:
                    duration = ""
            except Exception:
                time_str = "—"
                duration = ""

        # is_now: started in past, ends in future
        is_now = False
        try:
            sd = _start_dt(ev).astimezone()
            ed = _start_dt({"start": e}).astimezone() if e else None
            is_now = sd <= now and (ed is None or ed >= now)
        except Exception:
            pass

        # pill kind & text
        src = ev["_src"]
        if src == "holiday":
            pill = {"text": "节假日", "kind": "holiday"}
        elif src == "birthday":
            pill = {"text": "生日", "kind": "birthday"}
        elif is_now:
            pill = {"text": "now", "kind": "coral"}
        else:
            pill = {"text": "agenda", "kind": "dim"}

        out_events.append(
            {
                "time": time_str,
                "duration": duration,
                "title": title,
                "subtitle": location,
                "pill": pill,
                "is_now": is_now,
            }
        )

    return {
        "label_meta": f"Google · {len(out_events)} event{'s' if len(out_events) != 1 else ''}",
        "events": out_events,
    }


# ---- Tasks (todo.shopping_list) -----------------------------------------

def fetch_tasks(ws: WSClient) -> dict:
    try:
        resp = ws.request({"type": "todo/item/list", "entity_id": "todo.shopping_list"})
        items = (resp.get("result") or {}).get("items") or []
    except Exception as exc:
        print(f"[tasks] {exc}", flush=True)
        return {"label_meta": "—", "items": [], "source": "todo.shopping_list (unreachable)"}

    open_items = [i for i in items if i.get("status") != "completed"]
    done_items = [i for i in items if i.get("status") == "completed"]

    out = []
    for it in open_items[:5]:
        out.append({
            "label": it.get("summary") or "—",
            "meta": (it.get("due") or "")[:10] if it.get("due") else "",
            "done": False,
        })
    if done_items:
        last = done_items[0]
        out.append({
            "label": last.get("summary") or "—",
            "meta": "done",
            "done": True,
        })

    return {
        "label_meta": f"{len(open_items)} open · {len(done_items)} done",
        "items": out,
        "source": "via todo.shopping_list",
    }


# ---- Bulletin (todo.bulletin) -------------------------------------------

def fetch_bulletin(ws: WSClient) -> tuple[list[dict], int]:
    try:
        resp = ws.request({"type": "todo/item/list", "entity_id": "todo.bulletin"})
        items = (resp.get("result") or {}).get("items") or []
    except Exception:
        return [], 0

    out: list[dict] = []
    for it in items[:4]:
        if it.get("status") == "completed":
            continue
        summary = it.get("summary") or ""
        # Allow optional second line via " | " separator
        if " | " in summary:
            text, small = summary.split(" | ", 1)
        else:
            text, small = summary, ""
        out.append({
            "text": text.strip(),
            "small": small.strip(),
            "by": (it.get("due") or "now")[:10],
        })
    return out, len([i for i in items if i.get("status") != "completed"])


# ---- Footer system string -----------------------------------------------

def fetch_system_summary(states_dict: dict[str, dict]) -> str:
    bits = []
    try:
        config = ha_api.api("GET", "/api/config")
        ver = config.get("version", "unknown")
        bits.append(f"Home Assistant · {ver}")
    except Exception:
        bits.append("Home Assistant")

    # crude rollup: count entities, integrations
    bits.append(f"{len(states_dict)} entities")
    return " · ".join(bits)
