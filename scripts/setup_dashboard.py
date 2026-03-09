#!/usr/bin/env python3
"""Generate and apply a beautiful, area-organized HA dashboard with custom cards."""

import argparse
import json
import ssl
from ha_api import HA_URL, TOKEN


# ============================================================
# Helper functions — Original card types (kept for compatibility)
# ============================================================

def tile(entity, name=None, **kwargs):
    card = {"type": "tile", "entity": entity}
    if name:
        card["name"] = name
    card.update(kwargs)
    return card


def sensor_tile(entity, name, color=None):
    card = {"type": "tile", "entity": entity, "name": name}
    if color:
        card["color"] = color
    return card


def section(title, cards, columns=None):
    s = {"type": "grid", "title": title, "cards": cards}
    if columns:
        span = 4 // columns
        for c in cards:
            c.setdefault("layout_options", {})["grid_columns"] = span
    return s


# ============================================================
# Theme System — 修改 ACTIVE_THEME 切换主题
# ============================================================

THEMES = {
    # ---- 1. MD3 柠黄 ----
    # Material You 暖黄色调，圆润大卡片，轻盈无阴影
    "md3_yellow": {
        "view_css": """
  :host {
    --primary-color: #725C00;
    --accent-color: #725C00;
    --lovelace-background: #FFFBEC;
    --ha-card-background: #FFF1C1;
    --ha-card-border-radius: 28px;
    --ha-card-border-width: 0;
    --ha-card-box-shadow: none;
    --primary-background-color: #FFFBEC;
    --secondary-background-color: #F7E4A1;
  }
""",
        "card_css": """
ha-card {
  border-radius: 28px;
  border: none;
  box-shadow: none;
  transition: all 0.3s ease-out;
}
ha-card:active {
  transform: scale(0.97);
  filter: brightness(0.92);
}
""",
        "chip_css": "ha-card { --chip-box-shadow: none; --chip-background: none; --chip-spacing: 4px; }",
    },

    # ---- 2. Apple 家庭 ----
    # 灵感来自 Apple Home — 纯白卡片、柔和阴影、温润圆角
    # 浅灰画布 (#F2F2F7) 上的纯白卡片，通过微妙投影浮起
    # 圆角 22px 接近 Apple 大卡片语言，iOS 蓝 (#007AFF) 作为唯一点缀
    "apple_home": {
        "view_css": """
  :host {
    --primary-color: #007AFF;
    --accent-color: #34C759;
    --lovelace-background: #F2F2F7;
    --ha-card-background: #FFFFFF;
    --ha-card-border-radius: 22px;
    --ha-card-border-width: 0;
    --ha-card-box-shadow: 0 1px 4px rgba(0,0,0,0.06), 0 0.5px 1px rgba(0,0,0,0.04);
    --primary-background-color: #F2F2F7;
    --secondary-background-color: #E5E5EA;
    --primary-text-color: #1C1C1E;
    --secondary-text-color: #8E8E93;
    --disabled-text-color: #C7C7CC;
    --divider-color: rgba(0,0,0,0.06);
  }
""",
        "card_css": """
ha-card {
  border-radius: 22px;
  border: none;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06), 0 0.5px 1px rgba(0,0,0,0.04);
  transition: all 0.2s ease;
}
ha-card:active {
  transform: scale(0.98);
  filter: brightness(0.96);
}
""",
        "chip_css": "ha-card { --chip-box-shadow: none; --chip-background: rgba(0,0,0,0.03); --chip-spacing: 4px; --chip-border-radius: 18px; }",
    },

    # ---- 3. 科技拟物 ----
    # 暗色控制面板，微光边框，赛博朋克氛围
    # 深蓝黑底 (#080C12)，卡片以极细青色发光边框 (rgba 0,229,191) 悬浮
    # 14px 硬朗圆角 + inset 顶部高光模拟屏幕玻璃质感
    # 按压时边框增亮 + 外发光加强，像在按下控制台按钮
    "tech_scifi": {
        "view_css": """
  :host {
    --primary-color: #00E5BF;
    --accent-color: #00E5BF;
    --lovelace-background: #080C12;
    --ha-card-background: #0F1318;
    --ha-card-border-radius: 14px;
    --ha-card-border-width: 0;
    --ha-card-box-shadow: none;
    --primary-background-color: #080C12;
    --secondary-background-color: #151C25;
    --primary-text-color: #D8E2EC;
    --secondary-text-color: #506070;
    --disabled-text-color: #2A3540;
    --divider-color: rgba(0,229,191,0.08);
    --state-icon-active-color: #00E5BF;
  }
""",
        "card_css": """
ha-card {
  border-radius: 14px;
  border: 1px solid rgba(0,229,191,0.1);
  box-shadow: 0 0 20px rgba(0,229,191,0.03), inset 0 1px 0 rgba(255,255,255,0.02);
  transition: all 0.2s ease;
}
ha-card:active {
  transform: scale(0.98);
  border-color: rgba(0,229,191,0.2);
  box-shadow: 0 0 25px rgba(0,229,191,0.06);
}
""",
        "chip_css": "ha-card { --chip-box-shadow: none; --chip-background: rgba(0,229,191,0.05); --chip-spacing: 4px; --chip-border-radius: 10px; }",
    },

    # ---- 4. 极简暗黑 ----
    # Vercel / Linear 风格 — 纯黑极简，边框定义层次，无阴影
    # 纯黑 (#0A0A0A) 画布，卡片 (#111111) 仅比底色亮一个呼吸
    # 12px 利落圆角，rgba 6% 白色边框划分区域 — 像 Vercel 那样安静
    # 蓝色 (#3291FF) 仅用于激活态图标，克制到极致
    "minimal_dark": {
        "view_css": """
  :host {
    --primary-color: #FAFAFA;
    --accent-color: #3291FF;
    --lovelace-background: #0A0A0A;
    --ha-card-background: #111111;
    --ha-card-border-radius: 12px;
    --ha-card-border-width: 0;
    --ha-card-box-shadow: none;
    --primary-background-color: #0A0A0A;
    --secondary-background-color: #171717;
    --primary-text-color: #EDEDED;
    --secondary-text-color: #888888;
    --disabled-text-color: #444444;
    --divider-color: rgba(255,255,255,0.06);
    --state-icon-active-color: #3291FF;
  }
""",
        "card_css": """
ha-card {
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.06);
  box-shadow: none;
  transition: all 0.15s ease;
}
ha-card:active {
  transform: scale(0.98);
  background: #1A1A1A !important;
}
""",
        "chip_css": "ha-card { --chip-box-shadow: none; --chip-background: rgba(255,255,255,0.04); --chip-spacing: 4px; --chip-border-radius: 8px; }",
    },

    # ---- 5. 暖木小屋 ----
    # 暗色暖调，琥珀色点缀，深夜壁炉旁的控制台
    # 深棕底色 (#161210) 带红木色相，卡片 (#1E1915) 温暖厚实
    # 18px 圆角柔和但不幼稚，琥珀色 (#D4A574) 如烛光映在木面
    # 真实投影 (0 2px 8px) 给卡片重量感，按压时微微提亮像被火光照到
    "warm_cabin": {
        "view_css": """
  :host {
    --primary-color: #D4A574;
    --accent-color: #D4A574;
    --lovelace-background: #161210;
    --ha-card-background: #1E1915;
    --ha-card-border-radius: 18px;
    --ha-card-border-width: 0;
    --ha-card-box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    --primary-background-color: #161210;
    --secondary-background-color: #262018;
    --primary-text-color: #E8DDD0;
    --secondary-text-color: #8A7B6B;
    --disabled-text-color: #4A4035;
    --divider-color: rgba(212,165,116,0.08);
    --state-icon-active-color: #D4A574;
  }
""",
        "card_css": """
ha-card {
  border-radius: 18px;
  border: 1px solid rgba(212,165,116,0.06);
  box-shadow: 0 2px 8px rgba(0,0,0,0.25);
  transition: all 0.25s ease;
}
ha-card:active {
  transform: scale(0.97);
  filter: brightness(1.05);
}
""",
        "chip_css": "ha-card { --chip-box-shadow: none; --chip-background: rgba(212,165,116,0.06); --chip-spacing: 4px; --chip-border-radius: 14px; }",
    },
}

# ═══ 主题选择（命令行参数 > 默认值）═══
_parser = argparse.ArgumentParser(description="Deploy HA dashboard")
_parser.add_argument("--theme", "-t", choices=list(THEMES), default="md3_yellow",
                     help="主题名称 (default: md3_yellow)")
_args, _ = _parser.parse_known_args()
ACTIVE_THEME = _args.theme

_theme = THEMES[ACTIVE_THEME]
MD3_THEME_VARIABLES = _theme["view_css"]
MD3_STYLE = _theme["card_css"]
_CHIP_STYLE = _theme["chip_css"]
def md3_pill_select_style(
    height=48,
    padding=18,
    card_background=None,
    card_radius=None,
    icon_background="var(--secondary-background-color)",
    state_item_padding=None,
    pill_background="var(--secondary-background-color)",
    pill_border="none",
):
    card_bg_css = ""
    if card_background is not None or card_radius is not None:
        bg = card_background or "var(--ha-card-background)"
        radius = f"{card_radius}px" if card_radius is not None else "var(--ha-card-border-radius, 28px)"
        card_bg_css = f"""
ha-card {{
  background: {bg} !important;
  border-radius: {radius} !important;
  box-shadow: none !important;
  border: none !important;
}}
"""
    state_item_padding_css = f"  padding: {state_item_padding} !important;\n" if state_item_padding else ""
    return {
        ".": MD3_STYLE + card_bg_css + f"""
mushroom-state-item {{
  --mushroom-icon-background: {icon_background} !important;
{state_item_padding_css}}}
""",
        "mushroom-select-option-control$": {
            "mushroom-select$": f"""
            .mdc-select__anchor {{
              min-height: {height}px !important;
              border-radius: 999px !important;
              background: {pill_background} !important;
              padding: 0 {padding}px !important;
              border: {pill_border} !important;
              box-sizing: border-box !important;
            }}
            .mdc-line-ripple::before,
            .mdc-line-ripple::after {{
              border-bottom-width: 0 !important;
              border-bottom-style: none !important;
            }}
            .mdc-select__dropdown-icon {{
              fill: var(--secondary-text-color) !important;
            }}
            """,
            "ha-control-select-menu$": f"""
            .select .select-anchor {{
              min-height: {height}px !important;
              border-radius: 999px !important;
              background: {pill_background} !important;
              border: {pill_border} !important;
              box-sizing: border-box !important;
            }}
            .select .line {{
              display: none !important;
            }}
            mwc-menu {{
              --mdc-shape-medium: 16px !important;
            }}
            """,
            "ha-select$": f"""
            .mdc-select__anchor {{
              min-height: {height}px !important;
              border-radius: 999px !important;
              background: {pill_background} !important;
              border: {pill_border} !important;
              box-sizing: border-box !important;
            }}
            .mdc-line-ripple::before,
            .mdc-line-ripple::after {{
              border-bottom-width: 0 !important;
              border-bottom-style: none !important;
            }}
            """,
        },
    }


MD3_SELECT_STYLE = md3_pill_select_style()
MD3_SELECT_STYLE_CLEANING = md3_pill_select_style(
    height=40,
    padding=16,
    card_background="var(--secondary-background-color, rgba(128,128,128,0.05))",
    card_radius=12,
    icon_background="transparent",
    pill_background="var(--ha-card-background)",
    pill_border="1px solid var(--divider-color, rgba(0,0,0,0.12))",
)
MD3_SELECT_STYLE_CLEANING_COMPACT = md3_pill_select_style(
    height=32,
    padding=14,
    card_background="var(--secondary-background-color, rgba(128,128,128,0.05))",
    card_radius=12,
    icon_background="transparent",
    state_item_padding="0 4px",
    pill_background="var(--ha-card-background)",
    pill_border="1px solid var(--divider-color, rgba(0,0,0,0.12))",
)


def md3_icon_name_button_styles(min_height="110px", font_size="14px", padding="10px 8px"):
    card_styles = [
        {"padding": padding},
        {"border-radius": "16px"},
        {"background": "var(--md-sys-color-secondary-container, var(--secondary-background-color, rgba(128,128,128,0.12)))"},
        {"border": "none"},
        {"box-shadow": "none"},
        {"transition": "filter 0.16s ease, transform 0.16s ease"},
    ]
    if min_height:
        card_styles.append({"min-height": min_height})
    return {
        "card": card_styles,
        "grid": [
            {"grid-template-areas": "\"i n\""},
            {"grid-template-columns": "26px auto"},
            {"column-gap": "8px"},
            {"align-items": "center"},
            {"justify-content": "center"},
        ],
        "icon": [
            {"width": "26px"},
            {"height": "26px"},
            {"--mdc-icon-size": "26px"},
            {"color": "var(--md-sys-color-on-secondary-container, var(--primary-text-color))"},
        ],
        "name": [
            {"font-size": font_size},
            {"font-weight": "600"},
            {"color": "var(--md-sys-color-on-secondary-container, var(--primary-text-color))"},
        ],
    }


def md3_toggle_button(entity, label, icon, min_height="110px", font_size="14px", padding="10px 8px"):
    return {
        "type": "custom:button-card",
        "entity": entity,
        "name": label,
        "icon": icon,
        "show_state": False,
        "tap_action": {"action": "toggle"},
        "layout": "icon_name",
        "state": [{
            "value": "on",
            "styles": {
                "card": [
                    {"background": "var(--md-sys-color-primary, var(--primary-color))"},
                    {"border": "none"},
                    {"box-shadow": "none"},
                ],
                "icon": [{"color": "var(--md-sys-color-on-primary, #fff)"}],
                "name": [{"color": "var(--md-sys-color-on-primary, #fff)"}],
            },
        }],
        "styles": md3_icon_name_button_styles(min_height=min_height, font_size=font_size, padding=padding),
    }


def md3_service_button(name, icon, service, data=None, confirmation_text=None,
                       entity=None, min_height=None, font_size="14px", padding="10px 8px",
                       radius="16px", grid_columns=None):
    tap_action = {"action": "call-service", "service": service}
    if data:
        tap_action["data"] = data
    if confirmation_text:
        tap_action["confirmation"] = {"text": confirmation_text}

    styles = md3_icon_name_button_styles(min_height=min_height, font_size=font_size, padding=padding)
    styles["card"][1] = {"border-radius": radius}

    card = {
        "type": "custom:button-card",
        "name": name,
        "icon": icon,
        "show_state": False,
        "tap_action": tap_action,
        "layout": "icon_name",
        "styles": styles,
    }
    if entity:
        card["entity"] = entity
    if grid_columns:
        card["layout_options"] = {"grid_columns": grid_columns}
    return card


def mushroom_entity(entity, name=None, icon=None, icon_color=None):
    card = {
        "type": "custom:mushroom-entity-card", 
        "entity": entity,
        "card_mod": {"style": MD3_STYLE}
    }
    if name:
        card["name"] = name
    if icon:
        card["icon"] = icon
    if icon_color:
        card["icon_color"] = icon_color
    return card


def mushroom_light(entity, name=None, icon=None, is_group=False):
    card = {
        "type": "custom:mushroom-light-card",
        "entity": entity,
        "show_brightness_control": True,
        "show_color_temp_control": True,
        "use_light_color": True,
        "collapsible_controls": not is_group,
        "card_mod": {"style": MD3_STYLE},
    }
    if name:
        card["name"] = name
    if icon:
        card["icon"] = icon
    elif is_group:
        card["icon"] = "mdi:lightbulb-group"
    return card


def mushroom_climate(entity, name=None):
    card = {
        "type": "custom:mushroom-climate-card",
        "entity": entity,
        "show_temperature_control": True,
        "collapsible_controls": True,
        "hvac_modes": ["heat", "cool", "heat_cool", "auto", "fan_only", "off"],
        "card_mod": {"style": MD3_STYLE}
    }
    if name:
        card["name"] = name
    return card


def mushroom_climate_expanded(entity, name=None):
    card = {
        "type": "custom:mushroom-climate-card",
        "entity": entity,
        "show_temperature_control": True,
        "collapsible_controls": False,
        "hvac_modes": ["heat", "cool", "heat_cool", "auto", "fan_only", "off"],
        "card_mod": {"style": MD3_STYLE}
    }
    if name:
        card["name"] = name
    return card


def mushroom_fan_expanded(entity, name=None):
    card = {
        "type": "custom:mushroom-fan-card",
        "entity": entity,
        "show_percentage_control": True,
        "collapsible_controls": False,
        "card_mod": {"style": MD3_STYLE}
    }
    if name:
        card["name"] = name
    return card


def mushroom_cover(entity, name=None):
    card = {
        "type": "custom:mushroom-cover-card",
        "entity": entity,
        "show_buttons_control": True,
        "show_position_control": True,
        "card_mod": {"style": MD3_STYLE}
    }
    if name:
        card["name"] = name
    return card


def mushroom_fan(entity, name=None):
    card = {
        "type": "custom:mushroom-fan-card",
        "entity": entity,
        "show_percentage_control": True,
        "collapsible_controls": True,
        "card_mod": {"style": MD3_STYLE}
    }
    if name:
        card["name"] = name
    return card


def mushroom_chips(chips):
    return {
        "type": "custom:mushroom-chips-card",
        "chips": chips,
        "alignment": "center",
        "card_mod": {
            "style": _CHIP_STYLE
        }
    }


def mushroom_template(name, icon, icon_color, primary, secondary=None, tap_action=None):
    card = {
        "type": "custom:mushroom-template-card",
        "primary": primary,
        "secondary": secondary or "",
        "icon": icon,
        "icon_color": icon_color,
        "card_mod": {"style": MD3_STYLE}
    }
    if tap_action:
        card["tap_action"] = tap_action
    return card


def mushroom_select(entity, name=None, icon=None, icon_color=None, style=None):
    card = {
        "type": "custom:mushroom-select-card",
        "entity": entity,
        "card_mod": {"style": style or MD3_SELECT_STYLE}
    }
    if name:
        card["name"] = name
    if icon:
        card["icon"] = icon
    if icon_color:
        card["icon_color"] = icon_color
    return card


def tile_toggle(entity, name=None, icon=None):
    card = {
        "type": "tile",
        "entity": entity,
        "features": [{"type": "toggle"}],
        "features_position": "inline",
        "vertical": False,
        "layout_options": {"grid_columns": 4},
        "card_mod": {"style": MD3_STYLE},
    }
    if name:
        card["name"] = name
    if icon:
        card["icon"] = icon
    return card


def mushroom_media(entity, name=None, media_controls=None):
    card = {
        "type": "custom:mushroom-media-player-card",
        "entity": entity,
        "use_media_info": True,
        "show_volume_level": True,
        "media_controls": media_controls if media_controls is not None else ["on_off", "play_pause_stop", "previous", "next"],
        "volume_controls": ["volume_buttons", "volume_mute"],
        "collapsible_controls": True,
        "card_mod": {"style": MD3_STYLE}
    }
    if name:
        card["name"] = name
    return card


def mini_graph(entities, name=None, hours_to_show=24, line_width=2, height=80, grid_columns=None):
    card = {
        "type": "custom:mini-graph-card",
        "entities": entities,
        "hours_to_show": hours_to_show,
        "line_width": line_width,
        "height": height,
        "animate": True,
        "show": {"labels": True, "points": False},
        "card_mod": {"style": MD3_STYLE}
    }
    if name:
        card["name"] = name
    if grid_columns:
        card["layout_options"] = {"grid_columns": grid_columns}
    return card


def browser_mod_popup(title, cards):
    """Return a tap_action dict that opens a Browser Mod popup."""
    return {
        "action": "fire-dom-event",
        "browser_mod": {
            "service": "browser_mod.popup",
            "data": {
                "title": title,
                "content": {
                    "type": "vertical-stack",
                    "cards": cards,
                },
            },
        },
    }


# ============================================================
# Popup builders
# ============================================================

def env_popup_action():
    """Popup: environment detail with mini-graph + sensor cards."""
    temp_entity = "sensor.xiaomi_cn_2008215373_ua3a_temperature_p_3_7"
    humi_entity = "sensor.xiaomi_cn_2008215373_ua3a_relative_humidity_p_3_1"
    pm25_entity = "sensor.xiaomi_cn_2008215373_ua3a_pm2_5_density_p_3_4"
    pm10_entity = "sensor.xiaomi_cn_2008215373_ua3a_pm10_density_p_3_5"
    co2_entity = "sensor.xiaomi_cn_2008215373_ua3a_co2_density_p_3_8"
    hcho_entity = "sensor.xiaomi_cn_2008215373_ua3a_hcho_density_p_3_10"
    tvoc_entity = "sensor.xiaomi_cn_2008215373_ua3a_tvoc_density_p_3_9"

    cards = [
        mini_graph(
            [
                {"entity": temp_entity, "name": "温度"},
                {"entity": humi_entity, "name": "湿度", "y_axis": "secondary"},
            ],
            name="温湿度 24h",
            hours_to_show=24,
            height=120,
        ),
        mini_graph(
            [
                {"entity": pm25_entity, "name": "PM2.5"},
                {"entity": co2_entity, "name": "CO₂", "y_axis": "secondary"},
            ],
            name="空气质量 24h",
            hours_to_show=24,
            height=120,
        ),
        mushroom_entity(temp_entity, "温度", "mdi:thermometer", "orange"),
        mushroom_entity(humi_entity, "湿度", "mdi:water-percent", "cyan"),
        mushroom_entity(pm25_entity, "PM2.5", "mdi:blur", "green"),
        mushroom_entity(pm10_entity, "PM10", "mdi:blur-linear", "green"),
        mushroom_entity(co2_entity, "CO₂", "mdi:molecule-co2", "amber"),
        mushroom_entity(hcho_entity, "甲醛", "mdi:chemical-weapon", "deep-purple"),
        mushroom_entity(tvoc_entity, "TVOC", "mdi:air-filter", "indigo"),
    ]
    return browser_mod_popup("室内环境详情", cards)


def climate_popup_action(title, climate_cards):
    """Popup: climate detail with mushroom-climate cards."""
    return browser_mod_popup(title, climate_cards)


def claude_usage_card():
    """Homepage card: Claude Code usage progress."""
    entities = [_claude_5h_usage, _claude_7d_usage, _claude_extra_usage]

    title_js = (
        "[[["
        " const changed = states['" + _claude_5h_usage + "']?.last_changed;"
        " let syncText = '等待同步';"
        " if (changed) {"
        "   const d = new Date(changed);"
        "   if (!Number.isNaN(d.getTime())) {"
        "     syncText = `更新 ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;"
        "   }"
        " }"
        " return `<div><div style=\"font-size:16px;font-weight:700;color:var(--primary-text-color)\">Claude Code 配额</div><div style=\"margin-top:4px;font-size:12px;color:var(--secondary-text-color)\">${syncText}</div></div>`;"
        " ]]]"
    )

    badge_js = (
        "[[["
        " const extra = states['" + _claude_extra_usage + "'];"
        " const enabled = extra?.attributes?.enabled;"
        " const used = Number(extra?.state);"
        " const limit = Number(extra?.attributes?.monthly_limit);"
        " const displayLimit = Number.isFinite(limit) ? limit / 100 : NaN;"
        " if (enabled === false) {"
        "   return `<div style=\"padding:6px 10px;border-radius:999px;background:var(--secondary-background-color);font-size:12px;font-weight:600;color:var(--secondary-text-color)\">额外未启用</div>`;"
        " }"
        " if (!Number.isFinite(used)) {"
        "   return `<div style=\"padding:6px 10px;border-radius:999px;background:var(--secondary-background-color);font-size:12px;font-weight:600;color:var(--secondary-text-color)\">等待数据</div>`;"
        " }"
        " const usedText = `$${used.toFixed(2)}`;"
        " const limitText = Number.isFinite(displayLimit) && displayLimit > 0 ? ` / $${displayLimit.toFixed(0)}` : '';"
        " return `<div style=\"padding:6px 10px;border-radius:999px;background:var(--secondary-background-color);font-size:12px;font-weight:700;color:var(--primary-text-color)\">${usedText}${limitText}</div>`;"
        " ]]]"
    )

    progress_js = (
        "[[["
        " const sensor = (entityId) => states[entityId] || null;"
        " const clamp = (value) => Math.max(0, Math.min(100, value));"
        " const getPct = (entityId) => {"
        "   const raw = Number(sensor(entityId)?.state);"
        "   return Number.isFinite(raw) ? clamp(raw) : null;"
        " };"
        " const formatReset = (entityId) => {"
        "   const raw = sensor(entityId)?.attributes?.resets_at;"
        "   if (!raw) return '重置时间待同步';"
        "   const d = new Date(raw);"
        "   if (Number.isNaN(d.getTime())) return '重置时间待同步';"
        "   return `重置 ${String(d.getMonth() + 1).padStart(2,'0')}/${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;"
        " };"
        " const renderRow = (label, entityId, fill) => {"
        "   const value = getPct(entityId);"
        "   const width = value === null ? 0 : value;"
        "   const pctText = value === null ? '--%' : `${Math.round(value)}%`;"
        "   return `<div style=\"display:grid;gap:6px\">"
        "     <div style=\"display:flex;align-items:center;justify-content:space-between;gap:12px\">"
        "       <span style=\"font-size:13px;color:var(--secondary-text-color)\">${label}</span>"
        "       <span style=\"font-size:14px;font-weight:700;color:var(--primary-text-color)\">${pctText}</span>"
        "     </div>"
        "     <div style=\"height:10px;border-radius:999px;background:var(--secondary-background-color);overflow:hidden\">"
        "       <div style=\"height:100%;width:${width}%;border-radius:999px;background:${fill}\"></div>"
        "     </div>"
        "     <div style=\"font-size:11px;color:var(--secondary-text-color)\">${formatReset(entityId)}</div>"
        "   </div>`;"
        " };"
        " return `<div style=\"display:grid;gap:14px\">${renderRow('5 小时窗口', '" + _claude_5h_usage + "', 'var(--primary-color)')}${renderRow('7 天窗口', '" + _claude_7d_usage + "', 'var(--accent-color, var(--primary-color))')}</div>`;"
        " ]]]"
    )

    return {
        "type": "custom:button-card",
        "entity": _claude_5h_usage,
        "triggers_update": entities,
        "show_icon": False,
        "show_name": False,
        "show_state": False,
        "tap_action": {"action": "more-info"},
        "custom_fields": {
            "icon_area": (
                "[[[ return `<div style=\"width:56px;height:56px;border-radius:18px;background:var(--secondary-background-color);display:flex;align-items:center;justify-content:center\"><ha-icon icon='si:claude' style='--mdc-icon-size:30px;color:var(--primary-color)'></ha-icon></div>`; ]]]"
            ),
            "title_area": title_js,
            "extra_badge": badge_js,
            "usage_area": progress_js,
        },
        "styles": {
            "grid": [
                {"grid-template-areas": "'icon_area title_area extra_badge' 'usage_area usage_area usage_area'"},
                {"grid-template-columns": "56px minmax(0, 1fr) auto"},
                {"gap": "14px"},
                {"align-items": "start"},
            ],
            "card": [
                {"padding": "18px"},
                {"border-radius": "var(--ha-card-border-radius, 28px)"},
                {"background": "var(--ha-card-background)"},
                {"box-shadow": "none !important"},
                {"border": "none !important"},
            ],
            "custom_fields": {
                "icon_area": [{"grid-area": "icon_area"}],
                "title_area": [{"grid-area": "title_area"}, {"align-self": "center"}],
                "extra_badge": [{"grid-area": "extra_badge"}, {"justify-self": "end"}, {"align-self": "center"}],
                "usage_area": [{"grid-area": "usage_area"}, {"width": "100%"}],
            },
        },
        "layout_options": {"grid_columns": 4},
        "card_mod": {"style": MD3_STYLE},
    }


# ============================================================
# View 1: 首页 (Overview) — Redesigned
# ============================================================

# Sensors
_temp = "sensor.xiaomi_cn_2008215373_ua3a_temperature_p_3_7"
_humi = "sensor.xiaomi_cn_2008215373_ua3a_relative_humidity_p_3_1"
_pm25 = "sensor.xiaomi_cn_2008215373_ua3a_pm2_5_density_p_3_4"
_co2 = "sensor.xiaomi_cn_2008215373_ua3a_co2_density_p_3_8"
_claude_5h_usage = "sensor.claude_code_5h_yong_liang"
_claude_7d_usage = "sensor.claude_code_7d_yong_liang"
_claude_extra_usage = "sensor.claude_code_e_wai_yong_liang"

# Climate entities
_living_ac = "climate.lemesh_cn_2000792394_air02"
_master_ac = "climate.lemesh_cn_2000792363_air02"
_guest_ac = "climate.lemesh_cn_2000792396_air02"
_study_ac = "climate.lemesh_cn_2000792347_air02"
_bg_ac = "climate.lemesh_cn_2000794495_air02"
_west_kitchen_ac = "climate.lemesh_cn_2000792371_air02"
_floor_heat = "climate.tofan_cn_948856816_wk01"

home_view = {
    "title": "首页",
    "path": "home",
    "icon": "mdi:home",
    "type": "sections",
    "sections": [
        # --- Section 0: Welcome ---
        section("", [
            {
                "type": "custom:mushroom-title-card",
                "title": "{% set hour = now().hour %}"
                         "{% if hour < 6 %}🌙 夜深了"
                         "{% elif hour < 9 %}🌅 早上好"
                         "{% elif hour < 11 %}☀️ 上午好"
                         "{% elif hour < 14 %}🍱 中午好"
                         "{% elif hour < 18 %}🫖 下午好"
                         "{% else %}🌆 晚上好{% endif %}",
                "subtitle": "💡 {{ states.light | selectattr('state', 'eq', 'on') | rejectattr('entity_id', 'search', 'indicator_light|browser_mod|_deng_guang|_deng_dai|suo_you_deng_guang') | list | count }} 盏灯开启"
                            " · 🌡️ {{ states('" + _temp + "') }}°C"
                            " · 💧 {{ states('" + _humi + "') }}%"
                            " · 🌿 {{ states('" + _pm25 + "') }} μg/m³",
                "card_mod": {"style": MD3_STYLE},
            },
            {
                "type": "markdown",
                "content": (
                    "{% set raw = states('input_text.pokemon_data') %}"
                    "{% if raw not in ['unknown', 'unavailable', ''] %}"
                    "{% set d = raw | from_json %}"
                    "{% set sprite = states('input_text.pokemon_sprite') %}"
                    "{% set flavor = states('input_text.pokemon_flavor') %}"
                    '<img src="{{ sprite }}" '
                    'style="width:140px;display:block;margin:0 auto">\n\n'
                    "## #{{ d.id }} {{ d.cn }}\n"
                    "{{ d.en }}"
                    "{% if d.g %} · {{ d.g }}{% endif %}\n\n"
                    "**类型** {{ d.t }}　"
                    "**身高** {{ d.h }}　"
                    "**体重** {{ d.w }}\n\n"
                    "| HP | 攻击 | 防御 | 特攻 | 特防 | 速度 | 总计 |\n"
                    "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n"
                    "| {{ d.hp }}"
                    " | {{ d.atk }}"
                    " | {{ d['def'] }}"
                    " | {{ d.spa }}"
                    " | {{ d.spd }}"
                    " | {{ d.spe }}"
                    " | **{{ d.tot }}** |\n\n"
                    "{% if flavor not in ['unknown', 'unavailable', ''] %}"
                    "> {{ flavor }}\n\n"
                    "{% endif %}"
                    "{% else %}"
                    "*运行 `update_pokemon.py` 加载今日宝可梦*"
                    "{% endif %}"
                ),
                "card_mod": {"style": MD3_STYLE},
            },
        ]),

        # --- Section 1: 总览 ---
        section("总览", [
            # Weather & Environment Chips Combined
            mushroom_chips([
                # Weather Pill
                {
                    "type": "template",
                    "icon": "mdi:weather-cloudy",
                    "icon_color": "blue",
                    "content": "{{ states('weather.forecast_wo_de_jia') }} · {{ state_attr('weather.forecast_wo_de_jia', 'temperature') }}°C",
                    "tap_action": {"action": "navigate", "navigation_path": "/home"},
                },
                # Temperature Chip
                {
                    "type": "template",
                    "icon": "mdi:thermometer",
                    "icon_color": "orange",
                    "content": "{{ states('" + _temp + "') }}°C",
                    "tap_action": env_popup_action(),
                },
                # Humidity Chip
                {
                    "type": "template",
                    "icon": "mdi:water-percent",
                    "icon_color": "cyan",
                    "content": "{{ states('" + _humi + "') }}%",
                    "tap_action": env_popup_action(),
                },
                # Air Quality Chip
                {
                    "type": "template",
                    "icon": "mdi:blur",
                    "icon_color": "green",
                    "content": "{{ states('" + _pm25 + "') }} μg",
                    "tap_action": env_popup_action(),
                },
            ]),

            claude_usage_card(),

            # Temperature & Humidity Graph
            mini_graph(
                [
                    {"entity": _temp, "name": "温度"},
                    {"entity": _humi, "name": "湿度", "y_axis": "secondary"},
                ],
                name="温湿度 24h",
                hours_to_show=24,
                height=100,
            ),

            # Climate Grid (tap → popup with expanded mushroom cards)
            mushroom_template(
                "客厅", "mdi:sofa", "orange",
                primary="客厅",
                secondary="{{ state_attr('" + _living_ac + "', 'current_temperature') }}° · {{ states('" + _living_ac + "') }}",
                tap_action=climate_popup_action("客厅温控", [
                    mushroom_climate_expanded(_living_ac, "客厅空调"),
                    mushroom_climate_expanded(_bg_ac, "背景空调"),
                    mushroom_climate_expanded(_west_kitchen_ac, "西厨空调"),
                    mushroom_climate_expanded(_floor_heat, "地暖温控"),
                    mushroom_fan_expanded("fan.tofan_cn_948856816_wk01_s_3_air_fresh", "新风机"),
                ]),
            ),
            mushroom_template(
                "主卧", "mdi:bed-king", "deep-purple",
                primary="主卧",
                secondary="{{ state_attr('" + _master_ac + "', 'current_temperature') }}° · {{ states('" + _master_ac + "') }}",
                tap_action=climate_popup_action("主卧温控", [
                    mushroom_climate_expanded(_master_ac, "主卧空调"),
                ]),
            ),
            mushroom_template(
                "次卧", "mdi:bed", "blue",
                primary="次卧",
                secondary="{{ state_attr('" + _guest_ac + "', 'current_temperature') }}° · {{ states('" + _guest_ac + "') }}",
                tap_action=climate_popup_action("次卧温控", [
                    mushroom_climate_expanded(_guest_ac, "次卧空调"),
                ]),
            ),
            mushroom_template(
                "书房", "mdi:bookshelf", "green",
                primary="书房",
                secondary="{{ state_attr('" + _study_ac + "', 'current_temperature') }}° · {{ states('" + _study_ac + "') }}",
                tap_action=climate_popup_action("书房温控", [
                    mushroom_climate_expanded(_study_ac, "书房空调"),
                ]),
            ),

            # Scenes & Lock
            mushroom_template(
                "会客模式", "mdi:account-group", "amber",
                primary="会客模式",
                tap_action={"action": "call-service", "service": "scene.turn_on", "data": {"entity_id": "scene.hui_ke_mo_shi"}},
            ),
            mushroom_template(
                "影音模式", "mdi:movie-open", "blue",
                primary="影音模式",
                tap_action={"action": "call-service", "service": "scene.turn_on", "data": {"entity_id": "scene.ying_yin_mo_shi"}},
            ),
            mushroom_template(
                "睡眠模式", "mdi:weather-night", "indigo",
                primary="睡眠模式",
                tap_action={"action": "call-service", "service": "scene.turn_on", "data": {"entity_id": "scene.shui_mian_mo_shi"}},
            ),
            mushroom_template(
                "门锁", "mdi:lock", "amber",
                primary="绿米门锁",
                secondary="{{ '已上锁 · ' + relative_time(states.event.lumi_cn_1011935590_bzacn1_lock_locked_e_2_2.last_changed) + '前' if as_timestamp(states.event.lumi_cn_1011935590_bzacn1_lock_locked_e_2_2.last_changed) > as_timestamp(states.event.lumi_cn_1011935590_bzacn1_lock_opened_e_2_1.last_changed) else '已开锁 · ' + relative_time(states.event.lumi_cn_1011935590_bzacn1_lock_opened_e_2_1.last_changed) + '前' }}",
            ),
            mushroom_entity("sensor.lumi_cn_1011935590_bzacn1_battery_level_p_4_1", "门锁电量", "mdi:battery", "green"),
            mushroom_template(
                "重启", "mdi:restart", "red",
                primary="重启 HA",
                secondary="{{ relative_time(states.sensor.last_boot.last_changed) }}前启动",
                tap_action={
                    "action": "call-service",
                    "service": "homeassistant.restart",
                    "confirmation": {"text": "确定要重启 Home Assistant 吗？"},
                },
            ),
        ]),

        # --- Section 2: 全屋灯光控制 ---
        section("全屋灯光控制", [
            mushroom_light("light.suo_you_deng_guang", "所有灯光", "mdi:home-lightbulb", is_group=True),
            mushroom_light("light.ke_ting_deng_guang", "客厅灯光组", "mdi:sofa", is_group=True),
            mushroom_light("light.xi_chu_deng_guang", "西厨灯光组", "mdi:countertop", is_group=True),
            mushroom_light("light.chu_fang_deng_guang", "厨房灯光组", "mdi:stove", is_group=True),
            mushroom_light("light.zhu_wo_deng_guang", "主卧灯光组", "mdi:bed-king", is_group=True),
            mushroom_light("light.zhu_wei_deng_guang", "主卫灯光组", "mdi:shower-head", is_group=True),
            mushroom_light("light.ci_wo_deng_guang", "次卧灯光组", "mdi:bed", is_group=True),
            mushroom_light("light.ci_wei_deng_guang", "次卫灯光组", "mdi:toilet", is_group=True),
            mushroom_light("light.shu_fang_deng_guang", "书房灯光组", "mdi:bookshelf", is_group=True),
            mushroom_light("light.yang_tai_deng_guang", "阳台灯光组", "mdi:balcony", is_group=True),
            mushroom_light("light.quan_wu_zhu_deng_dai", "全屋主灯带 (Matter)", "mdi:led-strip-variant", is_group=True),
            mushroom_light("light.quan_wu_fen_wei_deng_dai", "全屋氛围灯带", "mdi:led-strip-variant-off", is_group=True),
        ]),

        # --- Section 3: 设备与影音 ---
        section("设备与影音", [
            mushroom_light("light.trytogo", "Trytogo", "mdi:lightbulb-group"),
            mushroom_select(
                "select.trytogo_gradient_scene",
                "Gradient Scene",
                "mdi:gradient-horizontal",
                "purple",
                style=MD3_SELECT_STYLE,
            ),
            mushroom_fan("fan.xiaomi_cn_2008215373_ua3a_s_2_air_purifier", "空气净化器"),
            mushroom_fan("fan.tofan_cn_948856816_wk01_s_3_air_fresh", "新风机"),
            mushroom_cover("cover.linp_cn_2079472416_ec1db_s_2_curtain", "客厅布帘"),
            mushroom_cover("cover.linp_cn_2079495198_ec1db_s_2_curtain", "客厅纱帘"),
            mushroom_cover("cover.bean_cn_1158897918_ct06_s_2_curtain", "主卧窗帘"),
            mushroom_cover("cover.bean_cn_1158901062_ct06_s_2_curtain", "次卧窗帘"),
            mushroom_cover("cover.xiaomi_cn_967167649_lyj3xs_s_2_airer", "晾衣架"),
            mushroom_media("media_player.tcl_85q10l_pro", "TCL 电视"),
            mushroom_media("media_player.xi_chu", "西厨音箱"),
            mushroom_media("media_player.xiaomi_cn_979970247_oh2", "小爱音箱"),
            mushroom_media("media_player.zhu_wo", "主卧音箱"),
        ]),

    ],
}


# ============================================================
# View 2: 灯光 (Lighting)
# ============================================================
lighting_view = {
    "title": "灯光",
    "path": "lighting",
    "icon": "mdi:lightbulb-group",
    "type": "sections",
    "sections": [
        # --- 全屋总控 ---
        section("全屋总控", [
            {
                "type": "custom:mushroom-title-card",
                "title": "💡 灯光控制",
                "subtitle": "{{ states.light | selectattr('state', 'eq', 'on') "
                            "| rejectattr('entity_id', 'search', 'indicator_light|browser_mod|_deng_guang|_deng_dai|suo_you_deng_guang') "
                            "| list | count }} 盏灯开启 · 共 {{ states.light "
                            "| rejectattr('entity_id', 'search', 'indicator_light|browser_mod|_deng_guang|_deng_dai|suo_you_deng_guang') "
                            "| list | count }} 盏",
                "card_mod": {"style": MD3_STYLE},
            },
            mushroom_light("light.suo_you_deng_guang", "所有灯光", "mdi:home-lightbulb", is_group=True),
            mushroom_light("light.quan_wu_zhu_deng_dai", "全屋主灯带 (Matter)", "mdi:led-strip-variant", is_group=True),
            mushroom_light("light.quan_wu_fen_wei_deng_dai", "全屋氛围灯带", "mdi:led-strip-variant-off", is_group=True),
            mushroom_entity("input_boolean.ren_lai_ren_zou_zi_dong_deng", "人来人走自动灯", "mdi:motion-sensor"),
        ]),
        # --- 客厅 ---
        section("🛋️ 客厅", [
            # 灯组
            mushroom_light("light.ke_ting_deng_guang", "客厅灯光组", "mdi:sofa", is_group=True),
            mushroom_light("light.ke_ting_dian_shi_gui_dao", "电视轨道", "mdi:track-light", is_group=True),
            mushroom_light("light.ke_ting_sha_fa_gui_dao", "沙发轨道", "mdi:track-light", is_group=True),
            mushroom_light("light.ke_ting_zhuo_zi_gui_dao", "桌子轨道", "mdi:track-light", is_group=True),
            # 单灯
            mushroom_light("light.intelligent_drive_power_supply_13", "折叠格栅灯", "mdi:light-recessed"),
            mushroom_light("light.intelligent_drive_power_supply_14", "格栅灯", "mdi:light-recessed"),
            mushroom_light("light.intelligent_power", "长格栅灯", "mdi:light-recessed"),
            mushroom_light("light.intelligent_drive_power_supply_15", "格栅灯", "mdi:light-recessed"),
            mushroom_light("light.intelligent_drive_power_supply_16", "泛光灯", "mdi:ceiling-light"),
            mushroom_light("light.intelligent_drive_power_supply_17", "格栅灯", "mdi:light-recessed"),
            mushroom_light("light.lemesh_cn_2023148762_wy0d02_s_2_light", "背景墙灯带", "mdi:led-strip"),
            mushroom_light("light.wlg_cn_949473222_wy0a06_s_2_light", "背景墙射灯 1", "mdi:spotlight-beam"),
            mushroom_light("light.wlg_cn_949429122_wy0a06_s_2_light", "背景墙射灯 2", "mdi:spotlight-beam"),
            mushroom_light("light.gdds_cn_2080299638_wy0a02_s_2_light", "节律筒射灯", "mdi:track-light"),
            mushroom_light("light.wlg_cn_949440999_wy0a06_s_2_light", "筒射灯 1", "mdi:track-light"),
            mushroom_light("light.wlg_cn_949442390_wy0a06_s_2_light", "筒射灯 2", "mdi:track-light"),
            mushroom_light("light.090615_cn_2000236373_milg05_s_2_light", "射灯 1", "mdi:spotlight-beam"),
            mushroom_light("light.090615_cn_2000254702_milg05_s_2_light", "射灯 2", "mdi:spotlight-beam"),
        ]),
        # --- 西厨 ---
        section("🍳 西厨", [
            mushroom_light("light.xi_chu_deng_guang", "西厨灯光组", "mdi:countertop", is_group=True),
            mushroom_light("light.intelligent_drive_power_supply", "厨房入口射灯", "mdi:spotlight-beam"),
            mushroom_light("light.intelligent_drive_power_supply_2", "背景墙", "mdi:wall-sconce-flat"),
            mushroom_light("light.intelligent_drive_power_supply_3", "进门射灯", "mdi:spotlight-beam"),
            mushroom_light("light.intelligent_drive_power_supply_4", "Spotlight", "mdi:spotlight-beam"),
            mushroom_light("light.lemesh_cn_2000921741_wy0d02_s_2_light", "岛台灯带", "mdi:led-strip"),
            mushroom_light("light.lemesh_cn_2023151493_wy0d02_s_2_light", "鞋柜灯带", "mdi:led-strip"),
            mushroom_light("light.wlg_cn_949413732_wy0a06_s_2_light", "筒射灯 1", "mdi:track-light"),
            mushroom_light("light.wlg_cn_949433559_wy0a06_s_2_light", "筒射灯 2", "mdi:track-light"),
            mushroom_light("light.wlg_cn_949433582_wy0a06_s_2_light", "筒射灯 3", "mdi:track-light"),
            mushroom_light("light.wlg_cn_949435731_wy0a06_s_2_light", "筒射灯 4", "mdi:track-light"),
        ]),
        # --- 厨房 ---
        section("🔪 厨房", [
            mushroom_light("light.chu_fang_deng_guang", "厨房灯光组", "mdi:stove", is_group=True),
            mushroom_light("light.intelligent_drive_power_supply_11", "平板灯", "mdi:ceiling-light"),
            mushroom_light("light.intelligent_drive_power_supply_12", "射灯", "mdi:spotlight-beam"),
        ]),
        # --- 主卧 ---
        section("🛏️ 主卧", [
            mushroom_light("light.zhu_wo_deng_guang", "主卧灯光组", "mdi:bed-king", is_group=True),
            mushroom_light("light.intelligent_drive_power_supply_22", "主灯", "mdi:ceiling-light"),
            mushroom_light("light.intelligent_drive_power_supply_20", "左射灯", "mdi:spotlight-beam"),
            mushroom_light("light.intelligent_drive_power_supply_21", "右射灯", "mdi:spotlight-beam"),
            mushroom_light("light.intelligent_drive_power_supply_18", "床头左射灯", "mdi:spotlight-beam"),
            mushroom_light("light.intelligent_drive_power_supply_19", "床头右射灯", "mdi:spotlight-beam"),
            mushroom_light("light.lemesh_cn_2020771536_wy0d02_s_2_light", "床头灯带", "mdi:led-strip"),
            mushroom_light("light.lemesh_cn_2020803689_wy0d02_s_2_light", "入口灯带", "mdi:led-strip"),
            mushroom_light("light.linp_cn_949882702_ld6bcw_s_2_light", "存在筒射灯", "mdi:motion-sensor"),
            mushroom_light("light.zhimi_cn_873345887_pa6_s_4_night_light", "马桶夜灯", "mdi:toilet"),
        ]),
        # --- 主卫 ---
        section("🚿 主卫", [
            mushroom_light("light.zhu_wei_deng_guang", "主卫灯光组", "mdi:shower-head", is_group=True),
            mushroom_light("light.xiaomi_cn_921633051_na2_s_2_light", "浴霸灯", "mdi:heat-wave"),
            mushroom_light("light.linp_cn_950194815_ld6bcw_s_2_light", "存在筒射灯", "mdi:motion-sensor"),
            mushroom_light("light.090615_cn_2000228017_milg05_s_2_light", "射灯 1", "mdi:spotlight-beam"),
            mushroom_light("light.090615_cn_2000257106_milg05_s_2_light", "射灯 2", "mdi:spotlight-beam"),
        ]),
        # --- 次卧 ---
        section("🛌 次卧", [
            mushroom_light("light.ci_wo_deng_guang", "次卧灯光组", "mdi:bed", is_group=True),
            mushroom_light("light.intelligent_drive_power_supply_5", "格栅灯", "mdi:light-recessed"),
            mushroom_light("light.090615_cn_2000281237_milg05_s_2_light", "射灯 1", "mdi:spotlight-beam"),
            mushroom_light("light.090615_cn_2000196741_milg05_s_2_light", "射灯 2", "mdi:spotlight-beam"),
            mushroom_light("light.linp_cn_949847136_ld6bcw_s_2_light", "存在筒射灯", "mdi:motion-sensor"),
            mushroom_light("light.lemesh_cn_2001035175_wy0d02_s_2_light", "入口灯带", "mdi:led-strip"),
            mushroom_light("light.moes_matter_light", "红色装饰灯", "mdi:lava-lamp"),
        ]),
        # --- 次卫 ---
        section("🚽 次卫", [
            mushroom_light("light.ci_wei_deng_guang", "次卫灯光组", "mdi:toilet", is_group=True),
            mushroom_light("light.yeelink_cn_945433772_v11_s_2_light", "浴霸灯", "mdi:heat-wave"),
            mushroom_light("light.linp_cn_949833026_ld6bcw_s_2_light", "存在筒射灯", "mdi:motion-sensor"),
            mushroom_light("light.090615_cn_2000254608_milg05_s_2_light", "射灯 1", "mdi:spotlight-beam"),
            mushroom_light("light.090615_cn_2000276840_milg05_s_2_light", "射灯 2", "mdi:spotlight-beam"),
        ]),
        # --- 书房 ---
        section("📚 书房", [
            mushroom_light("light.shu_fang_deng_guang", "书房灯光组", "mdi:bookshelf", is_group=True),
            mushroom_light("light.intelligent_drive_power_supply_6", "主灯", "mdi:ceiling-light"),
            mushroom_light("light.intelligent_drive_power_supply_8", "射灯 1", "mdi:spotlight-beam"),
            mushroom_light("light.intelligent_drive_power_supply_7", "射灯 2", "mdi:spotlight-beam"),
            mushroom_light("light.intelligent_drive_power_supply_9", "射灯 3", "mdi:spotlight-beam"),
            mushroom_light("light.intelligent_drive_power_supply_10", "射灯 4", "mdi:spotlight-beam"),
            mushroom_light("light.magical_homes_color_light_2", "书房灯带", "mdi:led-strip-variant"),
            mushroom_light("light.lemesh_cn_2000705436_wy0d02_s_2_light", "色温灯", "mdi:desk-lamp"),
        ]),
        # --- 阳台 ---
        section("🌿 阳台", [
            mushroom_light("light.yang_tai_deng_guang", "阳台灯光组", "mdi:balcony", is_group=True),
            mushroom_light("light.magical_homes_color_light", "灯带", "mdi:led-strip-variant"),
            mushroom_light("light.wlg_cn_949198312_wy0a06_s_2_light", "筒射灯 1", "mdi:track-light"),
            mushroom_light("light.wlg_cn_949459616_wy0a06_s_2_light", "筒射灯 2", "mdi:track-light"),
            mushroom_light("light.xiaomi_cn_967167649_lyj3xs_s_3_light", "晾衣机灯", "mdi:hanger"),
        ]),
    ],
}


# ============================================================
# View 3: 环境 (Environment)
# ============================================================
environment_view = {
    "title": "环境",
    "path": "environment",
    "icon": "mdi:thermometer-lines",
    "type": "sections",
    "sections": [
        # --- 客厅空气质量 (richest sensor set) ---
        section("🛋️ 客厅空气质量", [
            {
                "type": "custom:mushroom-title-card",
                "title": "客厅环境",
                "subtitle": "🌡️ {{ states('" + _temp + "') }}°C · 💧 {{ states('" + _humi + "') }}% · 🌿 PM2.5 {{ states('" + _pm25 + "') }}",
                "card_mod": {"style": MD3_STYLE},
            },
            mini_graph(
                [
                    {"entity": _temp, "name": "温度"},
                    {"entity": _humi, "name": "湿度", "y_axis": "secondary"},
                ],
                name="温湿度 24h",
                hours_to_show=24,
                height=120,
            ),
            mini_graph(
                [
                    {"entity": "sensor.xiaomi_cn_2008215373_ua3a_pm2_5_density_p_3_4", "name": "PM2.5", "color": "#4CAF50"},
                    {"entity": "sensor.xiaomi_cn_2008215373_ua3a_co2_density_p_3_8", "name": "CO₂", "y_axis": "secondary", "color": "#FF9800"},
                ],
                name="空气质量 24h",
                hours_to_show=24,
                height=120,
            ),
            mushroom_entity(_temp, "温度", "mdi:thermometer", "orange"),
            mushroom_entity(_humi, "湿度", "mdi:water-percent", "cyan"),
            mushroom_entity("sensor.xiaomi_cn_2008215373_ua3a_pm2_5_density_p_3_4", "PM2.5", "mdi:blur", "green"),
            mushroom_entity("sensor.xiaomi_cn_2008215373_ua3a_pm10_density_p_3_5", "PM10", "mdi:blur-linear", "green"),
            mushroom_entity("sensor.xiaomi_cn_2008215373_ua3a_co2_density_p_3_8", "CO₂", "mdi:molecule-co2", "amber"),
            mushroom_entity("sensor.xiaomi_cn_2008215373_ua3a_hcho_density_p_3_10", "甲醛", "mdi:chemical-weapon", "deep-purple"),
            mushroom_entity("sensor.xiaomi_cn_2008215373_ua3a_tvoc_density_p_3_9", "TVOC", "mdi:air-filter", "indigo"),
        ]),
        # --- 滤芯寿命 ---
        section("🔧 净化器滤芯", [
            mushroom_entity("sensor.xiaomi_cn_2008215373_ua3a_filter_life_level_p_4_1", "全效滤芯", "mdi:air-filter", "teal"),
            mushroom_entity("sensor.xiaomi_cn_2008215373_ua3a_filter_life_level_p_4_4", "碳素滤芯", "mdi:air-filter", "brown"),
            mushroom_entity("sensor.xiaomi_cn_2008215373_ua3a_filter_life_level_p_4_7", "中效滤芯", "mdi:air-filter", "grey"),
        ]),
        # --- 主卧传感器 ---
        section("🛏️ 主卧", [
            mushroom_entity("binary_sensor.linp_cn_949882702_ld6bcw_occupancy_status_p_5_1", "有人状态", "mdi:motion-sensor", "blue"),
            mushroom_entity("sensor.linp_cn_949882702_ld6bcw_illumination_p_5_5", "光照度", "mdi:brightness-5", "yellow"),
            mushroom_entity("sensor.xiaomi_cn_2000414477_w3_temperature_p_2_7", "温度", "mdi:thermometer", "orange"),
        ]),
        # --- 主卫传感器 ---
        section("🚿 主卫", [
            mushroom_entity("binary_sensor.linp_cn_1139276665_hb01_occupancy_status_p_2_1", "有人状态", "mdi:motion-sensor", "blue"),
            mushroom_entity("binary_sensor.linp_cn_950194815_ld6bcw_occupancy_status_p_5_1", "筒射灯人感", "mdi:motion-sensor", "blue"),
            mushroom_entity("sensor.xiaomi_cn_921633051_na2_relative_humidity_p_11_9", "湿度", "mdi:water-percent", "cyan"),
            mushroom_entity("sensor.xiaomi_cn_2042094243_w2_temperature_p_2_7", "温度", "mdi:thermometer", "orange"),
            mushroom_entity("sensor.linp_cn_1139276665_hb01_illumination_p_2_5", "光照度", "mdi:brightness-5", "yellow"),
        ]),
        # --- 次卧传感器 ---
        section("🛌 次卧", [
            mushroom_entity("binary_sensor.linp_cn_949847136_ld6bcw_occupancy_status_p_5_1", "有人状态", "mdi:motion-sensor", "blue"),
            mushroom_entity("sensor.linp_cn_949847136_ld6bcw_illumination_p_5_5", "光照度", "mdi:brightness-5", "yellow"),
            mushroom_entity("sensor.xiaomi_cn_2020906944_w1_temperature_p_2_7", "温度", "mdi:thermometer", "orange"),
        ]),
        # --- 次卫传感器 ---
        section("🚽 次卫", [
            mushroom_entity("binary_sensor.linp_cn_1139296986_hb01_occupancy_status_p_2_1", "有人状态", "mdi:motion-sensor", "blue"),
            mushroom_entity("binary_sensor.linp_cn_949833026_ld6bcw_occupancy_status_p_5_1", "筒射灯人感", "mdi:motion-sensor", "blue"),
            mushroom_entity("sensor.xiaomi_cn_2042194900_w2_temperature_p_2_7", "温度", "mdi:thermometer", "orange"),
            mushroom_entity("sensor.linp_cn_1139296986_hb01_illumination_p_2_5", "光照度", "mdi:brightness-5", "yellow"),
        ]),
        # --- 书房传感器 ---
        section("📚 书房", [
            mushroom_entity("sensor.xiaomi_cn_2021424647_w2_temperature_p_2_7", "温度", "mdi:thermometer", "orange"),
        ]),
        # --- 安全 ---
        section("🛡️ 安全监测", [
            mushroom_entity("binary_sensor.xiaomi_cn_blt_3_1n2u88p650c02_oh83w_submersion_state_p_2_1006", "水浸传感（浸没）", "mdi:water-alert", "red"),
            mushroom_entity("binary_sensor.xiaomi_cn_blt_3_1n2u88p650c02_oh83w_submersion_state_top_p_2_1123", "水浸传感（淋水）", "mdi:water-alert", "red"),
            mushroom_entity("sensor.xiaomi_cn_blt_3_1n2u88p650c02_oh83w_battery_level_p_3_1003", "水浸传感器电量", "mdi:battery", "green"),
        ]),
    ],
}


# ============================================================
# View 4: 空调 (Climate)
# ============================================================
climate_view = {
    "title": "空调",
    "path": "climate",
    "icon": "mdi:air-conditioner",
    "type": "sections",
    "sections": [
        # --- 客厅 ---
        section("🛋️ 客厅", [
            {
                "type": "custom:mushroom-title-card",
                "title": "客厅温控",
                "subtitle": "{{ state_attr('" + _living_ac + "', 'current_temperature') }}°C · {{ states('" + _living_ac + "') }}",
                "card_mod": {"style": MD3_STYLE},
            },
            mushroom_climate(_living_ac, "客厅空调"),
            mushroom_climate(_bg_ac, "背景空调"),
            mushroom_climate(_west_kitchen_ac, "西厨空调"),
            mushroom_climate(_floor_heat, "地暖温控"),
            mushroom_fan("fan.tofan_cn_948856816_wk01_s_3_air_fresh", "新风机"),
            mushroom_fan("fan.xiaomi_cn_2008215373_ua3a_s_2_air_purifier", "空气净化器"),
        ]),
        # --- 主卧 ---
        section("🛏️ 主卧", [
            mushroom_climate(_master_ac, "主卧空调"),
        ]),
        # --- 主卫浴霸 ---
        section("🚿 主卫浴霸", [
            mushroom_climate("climate.xiaomi_cn_921633051_na2", "浴霸 P1"),
            mushroom_entity("switch.xiaomi_cn_921633051_na2_ventilation_p_4_8", "换气", "mdi:fan", "cyan"),
        ]),
        # --- 次卧 ---
        section("🛌 次卧", [
            mushroom_climate(_guest_ac, "次卧空调"),
        ]),
        # --- 次卫浴霸 ---
        section("🚽 次卫浴霸", [
            mushroom_climate("climate.yeelink_cn_945433772_v11", "浴霸"),
            mushroom_entity("switch.yeelink_cn_945433772_v11_blow_p_3_2", "吹风", "mdi:hair-dryer", "orange"),
            mushroom_entity("switch.yeelink_cn_945433772_v11_heating_p_3_3", "加热", "mdi:radiator", "red"),
            mushroom_entity("switch.yeelink_cn_945433772_v11_ventilation_p_3_4", "换气", "mdi:fan", "cyan"),
        ]),
        # --- 书房 ---
        section("📚 书房", [
            mushroom_climate(_study_ac, "书房空调"),
        ]),
    ],
}


# ============================================================
# View 5: 杂项 (Misc — Curtains, Media, Network, Power, Lock)
# ============================================================
misc_view = {
    "title": "杂项",
    "path": "misc",
    "icon": "mdi:dots-hexagon",
    "type": "sections",
    "sections": [
        # --- 窗帘 & 晾衣架 ---
        section("🪟 窗帘与晾衣架", [
            mushroom_cover("cover.linp_cn_2079472416_ec1db_s_2_curtain", "客厅布帘"),
            mushroom_cover("cover.linp_cn_2079495198_ec1db_s_2_curtain", "客厅纱帘"),
            mushroom_cover("cover.bean_cn_1158897918_ct06_s_2_curtain", "主卧窗帘"),
            mushroom_cover("cover.bean_cn_1158901062_ct06_s_2_curtain", "次卧窗帘"),
            mushroom_cover("cover.xiaomi_cn_967167649_lyj3xs_s_2_airer", "晾衣架"),
        ]),
        # --- 影音 ---
        section("🎬 影音娱乐", [
            mushroom_media("media_player.tcl_85q10l_pro", "TCL 电视"),
            mushroom_media("media_player.ke_ting", "客厅音箱"),
            mushroom_media("media_player.xiaomi_cn_979970247_oh2", "小爱音箱"),
            mushroom_media("media_player.xi_chu", "西厨音箱"),
            mushroom_media("media_player.zhu_wo", "主卧音箱"),
        ]),
        # --- 网络 ---
        section("🌐 网络", [
            {
                "type": "custom:mushroom-title-card",
                "title": "家庭网络",
                "subtitle": "{{ states('sensor.xiaomi_cn_864626102_rd08_connected_device_number_p_2_3') }} 台设备在线",
                "card_mod": {"style": MD3_STYLE},
            },
            mushroom_entity("sensor.xiaomi_cn_864626102_rd08_download_speed_p_2_1", "下载速度", "mdi:download-network", "blue"),
            mushroom_entity("sensor.xiaomi_cn_864626102_rd08_upload_speed_p_2_2", "上传速度", "mdi:upload-network", "green"),
            mushroom_entity("sensor.xiaomi_cn_864626102_rd08_connected_device_number_p_2_3", "连接设备数", "mdi:devices", "amber"),
        ]),
        # --- 用电监测 ---
        section("⚡ 用电监测", [
            mushroom_entity("sensor.yeelink_cn_2044786630_plug1_power_consumption_p_3_1", "轨道插座耗电", "mdi:lightning-bolt", "orange"),
            mushroom_entity("sensor.yeelink_cn_2044786630_plug1_electric_power_p_3_2", "轨道插座功率", "mdi:flash", "orange"),
            mushroom_entity("sensor.lumi_cn_551733220_acn032_power_consumption_p_10_1", "妙控开关耗电", "mdi:lightning-bolt", "amber"),
            mushroom_entity("sensor.lumi_cn_551733220_acn032_electric_power_p_10_6", "妙控开关功率", "mdi:flash", "amber"),
        ]),
        # --- 门锁 ---
        section("🔐 门锁", [
            mushroom_template(
                "门锁", "mdi:lock", "amber",
                primary="绿米门锁",
                secondary="{{ '已上锁 · ' + relative_time(states.event.lumi_cn_1011935590_bzacn1_lock_locked_e_2_2.last_changed) + '前' "
                          "if as_timestamp(states.event.lumi_cn_1011935590_bzacn1_lock_locked_e_2_2.last_changed) > "
                          "as_timestamp(states.event.lumi_cn_1011935590_bzacn1_lock_opened_e_2_1.last_changed) "
                          "else '已开锁 · ' + relative_time(states.event.lumi_cn_1011935590_bzacn1_lock_opened_e_2_1.last_changed) + '前' }}",
            ),
            mushroom_entity("sensor.lumi_cn_1011935590_bzacn1_battery_level_p_4_1", "门锁电量", "mdi:battery", "green"),
        ]),
    ],
}


# ============================================================
_washer_state = "sensor.xi_yi_ji_machine_state"
_washer_job = "sensor.xi_yi_ji_job_state"
_washer_done = "sensor.xi_yi_ji_completion_time"
_dryer_state = "sensor.hong_gan_ji_machine_state"
_dryer_job = "sensor.hong_gan_ji_job_state"
_dryer_done = "sensor.hong_gan_ji_completion_time"
_dish_state = "sensor.xi_wan_ji_operation_state"
_dish_progress = "sensor.xi_wan_ji_program_progress"
_dish_done = "sensor.xi_wan_ji_program_finish_time"

_washer_jobs = ("{'wash':'洗涤','rinse':'漂洗','spin':'脱水','drying':'烘干',"
                "'pre_wash':'预洗','air_wash':'空气洗','cooling':'冷却',"
                "'weight_sensing':'称重','wrinkle_prevent':'防皱',"
                "'delay_wash':'预约中','finish':'已完成','ai_wash':'AI洗涤',"
                "'ai_rinse':'AI漂洗','ai_spin':'AI脱水','freeze_protection':'防冻',"
                "'none':'空闲'}")

_dryer_jobs = ("{'drying':'烘干中','cooling':'冷却','refreshing':'清新',"
               "'weight_sensing':'称重','wrinkle_prevent':'防皱',"
               "'delay_wash':'预约中','finished':'已完成','dehumidifying':'除湿',"
               "'ai_drying':'AI烘干','sanitizing':'杀菌','internal_care':'内筒自洁',"
               "'freeze_protection':'防冻','continuous_dehumidifying':'持续除湿',"
               "'thawing_frozen_inside':'内筒解冻','none':'空闲'}")

def dishwasher_button_card():
    """Custom button-card: 洗碗机综合面板."""
    _dw_entities = [
        "sensor.xi_wan_ji_operation_state", "sensor.xi_wan_ji_program_progress",
        "sensor.xi_wan_ji_program_finish_time", "sensor.xi_wan_ji_door",
        "select.xi_wan_ji_selected_program", "switch.xi_wan_ji_vario_speed",
        "switch.xi_wan_ji_hygiene", "switch.xi_wan_ji_brilliance_dry",
    ]
    state_map_js = "const sm = {'ready':'就绪','run':'运行中','pause':'已暂停','finished':'已完成','delayed_start':'延时启动','error':'故障','inactive':'关机','aborting':'终止中'};"

    def _toggle_btn(entity, label, icon):
        return md3_toggle_button(entity, label, icon, min_height="110px", font_size="14px", padding="10px 6px")

    return {
        "type": "custom:button-card",
        "entity": "sensor.xi_wan_ji_operation_state",
        "triggers_update": _dw_entities,
        "show_icon": False, "show_name": False, "show_state": False,
        "custom_fields": {
            "icon_area": "[[[ const os = entity.state; const isRun = os === 'run'; const color = isRun ? 'var(--primary-color)' : 'var(--disabled-text-color)'; return `<div style=\"width:52px;height:52px;border-radius:14px;background:var(--secondary-background-color, rgba(128,128,128,0.08));display:flex;align-items:center;justify-content:center\"><ha-icon icon='mdi:dishwasher' style='--mdc-icon-size:32px;color:${color}'></ha-icon></div>`; ]]]",
            "status_text": "[[[ " + state_map_js + " const os = entity.state; return `<span style=\"font-size:18px;font-weight:600;color:var(--primary-text-color)\">${sm[os] || os}</span>`; ]]]",
            "progress_line": "[[[ const os = entity.state; if (os !== 'run') return '<span style=\"font-size:13px;color:var(--secondary-text-color)\">准备就绪</span>'; const pct = states['sensor.xi_wan_ji_program_progress'].state; return `<span style=\"font-size:13px;color:var(--secondary-text-color)\">进行中 · ${pct}%</span>`; ]]]",
            "stat_badges": "[[[ const door = states['sensor.xi_wan_ji_door'].state; const color = door === 'closed' ? 'var(--secondary-text-color)' : 'var(--error-color)'; return `<div style=\"background:${color}15;color:${color};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:bold\">门 ${door === 'closed' ? '已关' : '未关'}</div>`; ]]]",
            "prog": {"card": {"type": "custom:mushroom-select-card", "entity": "select.xi_wan_ji_selected_program", "name": "程序", "icon": "mdi:clipboard-list", "card_mod": {"style": MD3_SELECT_STYLE_CLEANING}}},
            "spacer": "",
            "btn1": {"card": _toggle_btn("switch.xi_wan_ji_vario_speed", "加速", "mdi:speedometer")},
            "btn2": {"card": _toggle_btn("switch.xi_wan_ji_hygiene", "杀菌", "mdi:bacteria")},
            "btn3": {"card": _toggle_btn("switch.xi_wan_ji_brilliance_dry", "烘干", "mdi:shimmer")}
        },
        "styles": {
            "grid": [
                {"grid-template-areas": "'icon_area status_text stat_badges' 'icon_area progress_line stat_badges' 'spacer prog btn1' 'spacer btn2 btn3'"},
                {"grid-template-columns": "52px repeat(2, minmax(0, 1fr))"}, {"gap": "12px"}, {"justify-items": "stretch"}, {"align-items": "start"}
            ],
            "card": [{"padding": "16px"}, {"border-radius": "28px"}, {"background": "var(--ha-card-background)"}, {"box-shadow": "none !important"}, {"border": "none !important"}],
            "custom_fields": {
                "icon_area": [{"grid-area": "icon_area"}],
                "status_text": [{"grid-area": "status_text"}, {"align-self": "end"}],
                "progress_line": [{"grid-area": "progress_line"}, {"align-self": "start"}],
                "stat_badges": [{"grid-area": "stat_badges"}, {"justify-self": "end"}, {"align-self": "start"}],
                "prog": [{"grid-area": "prog"}, {"width": "100%"}],
                "spacer": [{"grid-area": "spacer"}],
                "btn1": [{"grid-area": "btn1"}, {"width": "100%"}],
                "btn2": [{"grid-area": "btn2"}, {"width": "100%"}],
                "btn3": [{"grid-area": "btn3"}, {"width": "100%"}]
            }
        },
        "layout_options": {"grid_columns": 4},
        "card_mod": {"style": MD3_STYLE}
    }

def washer_button_card():
    """Custom button-card: 洗衣机综合面板."""
    _entities = [_washer_state, _washer_job, _washer_done, "select.xi_yi_ji", "select.xi_yi_ji_water_temperature", "select.xi_yi_ji_spin_level", "switch.xi_yi_ji_bubble_soak", "sensor.xi_yi_ji_power"]
    state_map_js = "const sm = " + _washer_jobs.replace("'", '"') + ";"

    return {
        "type": "custom:button-card",
        "entity": _washer_state, "triggers_update": _entities,
        "show_icon": False, "show_name": False, "show_state": False,
        "custom_fields": {
            "icon_area": "[[[ const os = entity.state; const isRun = os === 'run'; const color = isRun ? 'var(--cyan-color, #00BCD4)' : 'var(--disabled-text-color)'; return `<div style=\"width:52px;height:52px;border-radius:14px;background:var(--secondary-background-color, rgba(128,128,128,0.08));display:flex;align-items:center;justify-content:center\"><ha-icon icon='mdi:washing-machine' class='${isRun ? \"spin-icon\" : \"\"}' style='--mdc-icon-size:32px;color:${color}'></ha-icon></div>`; ]]]",
            "status_text": "[[[ " + state_map_js + " const os = entity.state; const js = states['" + _washer_job + "'].state; const label = os === 'run' ? sm[js] || js : (os === 'pause' ? '已暂停' : '待机'); return `<span style=\"font-size:18px;font-weight:600;color:var(--primary-text-color)\">${label}</span>`; ]]]",
            "progress_line": "[[[ const done = states['" + _washer_done + "'].state; if (!done || done === 'unknown') return '<span style=\"font-size:13px;color:var(--secondary-text-color)\">准备就绪</span>'; const d = new Date(done); return `<span style=\"font-size:13px;color:var(--secondary-text-color)\">预计 ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')} 完成</span>`; ]]]",
            "stat_badges": "[[[ const pwr = states['sensor.xi_yi_ji_power'].state || 0; return `<div style=\"background:var(--amber-color)20;color:var(--amber-color);padding:2px 8px;border-radius:10px;font-size:11px;font-weight:bold\">${pwr} W</div>`; ]]]",
            "prog": {"card": {"type": "custom:mushroom-select-card", "entity": "select.xi_yi_ji", "name": "模式", "icon": "mdi:play-pause", "card_mod": {"style": MD3_SELECT_STYLE_CLEANING}}},
            "spacer": "",
            "btn1": {"card": {"type": "custom:mushroom-select-card", "entity": "select.xi_yi_ji_water_temperature", "name": "水温", "icon": "mdi:thermometer", "card_mod": {"style": MD3_SELECT_STYLE_CLEANING}}},
            "btn2": {"card": {"type": "custom:mushroom-select-card", "entity": "select.xi_yi_ji_spin_level", "name": "转速", "icon": "mdi:rotate-3d", "card_mod": {"style": MD3_SELECT_STYLE_CLEANING}}},
            "btn3": {"card": md3_toggle_button("switch.xi_yi_ji_bubble_soak", "泡泡净", "mdi:chart-bubble", min_height="110px", font_size="13px", padding="10px 8px")}
        },
        "styles": {
            "grid": [
                {"grid-template-areas": "'icon_area status_text stat_badges' 'icon_area progress_line stat_badges' 'spacer prog btn1' 'spacer btn2 btn3'"},
                {"grid-template-columns": "52px repeat(2, minmax(0, 1fr))"}, {"gap": "12px"}, {"justify-items": "stretch"}, {"align-items": "start"}
            ],
            "card": [{"padding": "16px"}, {"border-radius": "28px"}, {"background": "var(--ha-card-background)"}, {"box-shadow": "none !important"}, {"border": "none !important"}],
            "custom_fields": {
                "icon_area": [{"grid-area": "icon_area"}],
                "status_text": [{"grid-area": "status_text"}, {"align-self": "end"}],
                "progress_line": [{"grid-area": "progress_line"}, {"align-self": "start"}],
                "stat_badges": [{"grid-area": "stat_badges"}, {"justify-self": "end"}, {"align-self": "start"}],
                "prog": [{"grid-area": "prog"}, {"width": "100%"}],
                "spacer": [{"grid-area": "spacer"}],
                "btn1": [{"grid-area": "btn1"}, {"width": "100%"}],
                "btn2": [{"grid-area": "btn2"}, {"width": "100%"}],
                "btn3": [{"grid-area": "btn3"}, {"width": "100%"}]
            }
        },
        "extra_styles": "@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } } .spin-icon { animation: spin 3s linear infinite; }",
        "layout_options": {"grid_columns": 4},
        "card_mod": {"style": MD3_STYLE}
    }

def dryer_button_card():
    """Custom button-card: 烘干机综合面板."""
    _entities = [_dryer_state, _dryer_job, _dryer_done, "select.hong_gan_ji", "switch.hong_gan_ji_wrinkle_prevent", "sensor.hong_gan_ji_power"]
    state_map_js = "const sm = " + _dryer_jobs.replace("'", '"') + ";"
    
    return {
        "type": "custom:button-card",
        "entity": _dryer_state, "triggers_update": _entities,
        "show_icon": False, "show_name": False, "show_state": False,
        "custom_fields": {
            "icon_area": "[[[ const os = entity.state; const isRun = os === 'run'; const color = isRun ? 'var(--orange-color, #FF9800)' : 'var(--disabled-text-color)'; return `<div style=\"width:52px;height:52px;border-radius:14px;background:var(--secondary-background-color, rgba(128,128,128,0.08));display:flex;align-items:center;justify-content:center\"><ha-icon icon='mdi:tumble-dryer' style='--mdc-icon-size:32px;color:${color}'></ha-icon></div>`; ]]]",
            "status_text": "[[[ " + state_map_js + " const os = entity.state; const js = states['" + _dryer_job + "'].state; const label = os === 'run' ? sm[js] || js : '待机'; return `<span style=\"font-size:18px;font-weight:600;color:var(--primary-text-color)\">${label}</span>`; ]]]",
            "progress_line": "[[[ const done = states['" + _dryer_done + "'].state; if (!done || done === 'unknown') return '<span style=\"font-size:13px;color:var(--secondary-text-color)\">准备就绪</span>'; const d = new Date(done); return `<span style=\"font-size:13px;color:var(--secondary-text-color)\">预计 ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')} 完成</span>`; ]]]",
            "stat_badges": "[[[ const pwr = states['sensor.hong_gan_ji_power'].state || 0; return `<div style=\"background:var(--amber-color)20;color:var(--amber-color);padding:2px 8px;border-radius:10px;font-size:11px;font-weight:bold\">${pwr} W</div>`; ]]]",
            "prog": {"card": {"type": "custom:mushroom-select-card", "entity": "select.hong_gan_ji", "name": "模式", "icon": "mdi:play-pause", "card_mod": {"style": MD3_SELECT_STYLE_CLEANING}}},
            "spacer": "",
            "btn1": {"card": md3_toggle_button("switch.hong_gan_ji_wrinkle_prevent", "防皱", "mdi:hanger", min_height="110px", font_size="14px", padding="10px")}
        },
        "styles": {
            "grid": [
                {"grid-template-areas": "'icon_area status_text stat_badges' 'icon_area progress_line stat_badges' 'spacer prog btn1'"},
                {"grid-template-columns": "52px repeat(2, minmax(0, 1fr))"}, {"gap": "12px"}, {"justify-items": "stretch"}, {"align-items": "start"}
            ],
            "card": [{"padding": "16px"}, {"border-radius": "28px"}, {"background": "var(--ha-card-background)"}, {"box-shadow": "none !important"}, {"border": "none !important"}],
            "custom_fields": {
                "icon_area": [{"grid-area": "icon_area"}],
                "status_text": [{"grid-area": "status_text"}, {"align-self": "end"}],
                "progress_line": [{"grid-area": "progress_line"}, {"align-self": "start"}],
                "stat_badges": [{"grid-area": "stat_badges"}, {"justify-self": "end"}, {"align-self": "start"}],
                "spacer": [{"grid-area": "spacer"}],
                "prog": [{"grid-area": "prog"}, {"width": "100%"}],
                "btn1": [{"grid-area": "btn1"}, {"width": "100%"}]
            }
        },
        "layout_options": {"grid_columns": 4},
        "card_mod": {"style": MD3_STYLE}
    }

# ============================================================
# View: 宠物 (PetKit)
# ============================================================

_nova_pic = "https://img5.petkit.cn/pavatar/2022/3/20/623692432ccd54000d56c5f9gXZJosh8G"
_nova_weight = "sensor.nova_last_weight_measurement"
_nova_use_date = "sensor.nova_last_use_date"
_nova_use_dur = "sensor.nova_last_use_duration"

_litter_state = "sensor.zhi_neng_mao_ce_suo_max_state"
_litter_event = "sensor.zhi_neng_mao_ce_suo_max_last_event"
_litter_weight = "sensor.zhi_neng_mao_ce_suo_max_litter_weight"
_litter_level = "sensor.zhi_neng_mao_ce_suo_max_litter_level"
_litter_times = "sensor.zhi_neng_mao_ce_suo_max_times_used"
_litter_avg = "sensor.zhi_neng_mao_ce_suo_max_average_use"
_litter_n50 = "sensor.zhi_neng_mao_ce_suo_max_odor_eliminator_n50_left_days"
_litter_used_by = "sensor.zhi_neng_mao_ce_suo_max_last_used_by"
_litter_sand_lack = "binary_sensor.zhi_neng_mao_ce_suo_max_sand_lack"
_litter_bin_full = "binary_sensor.zhi_neng_mao_ce_suo_max_wastebin_filled"
_litter_bin_present = "binary_sensor.zhi_neng_mao_ce_suo_max_wastebin_presence"
_litter_occupied = "binary_sensor.zhi_neng_mao_ce_suo_max_toilet_occupied"

_fountain_battery = "sensor.yin_shui_ji_max_zhen_wu_xian_battery"
_fountain_filter = "sensor.yin_shui_ji_max_zhen_wu_xian_filter_remaining"
_fountain_drinks = "sensor.yin_shui_ji_max_zhen_wu_xian_drink_times"
_fountain_water = "sensor.yin_shui_ji_max_zhen_wu_xian_purified_water"
_fountain_water_lack = "binary_sensor.yin_shui_ji_max_zhen_wu_xian_water_lack_warning"

_feeder_food_level = "sensor.mmgg_cn_467135245_inland_pet_food_left_level_p_2_6"
_feeder_desiccant = "sensor.mmgg_cn_467135245_inland_desiccant_left_time_p_11_2"
_feeder_plan_unit = "number.mmgg_cn_467135245_inland_feedplan_unit_p_5_8"
_feeder_plan_ctrl = "number.mmgg_cn_467135245_inland_feedplan_contr_p_5_5"
_feeder_feed_action = "notify.mmgg_cn_467135245_inland_pet_food_out_a_2_1"
_feeder_feed_success = "event.mmgg_cn_467135245_inland_feedsuccess_e_4_1"
_feeder_daily_total = "counter.pet_feeder_daily_portions"


def pet_profile_pill_card():
    """Compact MD3 pill card for pet profile."""
    return {
        "type": "custom:button-card",
        "entity": _nova_weight,
        "triggers_update": [_nova_weight, _nova_use_date, _nova_use_dur, _fountain_drinks, _litter_times],
        "show_icon": False,
        "show_name": False,
        "show_state": False,
        "tap_action": {"action": "none"},
        "custom_fields": {
            "avatar": f"<img src='{_nova_pic}' style='width:44px;height:44px;border-radius:50%;object-fit:cover;display:block'>",
            "info": (
                "[[[ "
                f"const wt = states['{_nova_weight}']?.state ?? '-'; "
                f"const used = states['{_nova_use_date}']?.state ?? '-'; "
                f"const dur = states['{_nova_use_dur}']?.state ?? '-'; "
                f"const drinks = states['{_fountain_drinks}']?.state ?? '-'; "
                f"const litter = states['{_litter_times}']?.state ?? '-'; "
                "const usedText = (used && used !== 'unknown' && used.length >= 16) ? used.slice(5, 16) : used; "
                "return `<div style=\"display:flex;flex-direction:column;gap:2px\">"
                "<span style=\"font-size:15px;font-weight:600;color:var(--md-sys-color-on-secondary-container, var(--primary-text-color))\">Nova</span>"
                "<span style=\"font-size:12px;color:var(--md-sys-color-on-secondary-container, var(--secondary-text-color))\">"
                "${wt} kg · 上次 ${usedText} · ${dur}s</span>"
                "<span style=\"font-size:12px;color:var(--md-sys-color-on-secondary-container, var(--secondary-text-color))\">"
                "饮水 ${drinks} 次 · 上厕 ${litter} 次</span></div>`; "
                "]]]"
            ),
        },
        "styles": {
            "grid": [
                {"grid-template-areas": "\"avatar info\""},
                {"grid-template-columns": "44px minmax(0, 1fr)"},
                {"column-gap": "10px"},
                {"align-items": "center"},
            ],
            "card": [
                {"padding": "10px 14px"},
                {"min-height": "62px"},
                {"border-radius": "999px"},
                {"background": "var(--md-sys-color-secondary-container, var(--secondary-background-color, rgba(128,128,128,0.12)))"},
                {"box-shadow": "none"},
                {"border": "none"},
            ],
            "custom_fields": {
                "avatar": [{"grid-area": "avatar"}],
                "info": [{"grid-area": "info"}],
            },
        },
        "layout_options": {"grid_columns": 4},
    }


def litter_box_card():
    """Custom button-card: 猫厕所MAX 综合面板."""
    _entities = [
        _litter_state, _litter_event, _litter_weight, _litter_level,
        _litter_times, _litter_avg, _litter_n50, _litter_used_by,
        _litter_sand_lack, _litter_bin_full, _litter_occupied,
    ]
    state_map_js = 'const sm = {"idle":"空闲","auto_cleaning":"自动清理中","manual_cleaning":"手动清理中","dumping_litter":"倾空猫砂中","leveling_litter":"抚平猫砂中","resetting":"复位中","paused":"已暂停","deodorizing":"除臭中"};'
    event_map_js = 'const em = {"auto_cleaning_completed":"自动清理完成","manual_cleaning_completed":"手动清理完成","dumping_completed":"倾空完成","leveling_completed":"抚平完成","deodorizing_completed":"除臭完成","pet_in":"宠物进入","pet_out":"宠物离开","auto_cleaning_started":"自动清理开始","no_events_recorded":"暂无事件"};'

    return {
        "type": "custom:button-card",
        "entity": _litter_state,
        "triggers_update": _entities,
        "show_icon": False, "show_name": False, "show_state": False,
        "custom_fields": {
            "icon_area": "[[[ const st = entity.state; const busy = st !== 'idle'; const color = busy ? 'var(--md-sys-color-primary, var(--primary-color))' : 'var(--md-sys-color-on-surface-variant, var(--secondary-text-color))'; return `<div style=\"width:52px;height:52px;border-radius:16px;background:var(--md-sys-color-surface-container-high, var(--secondary-background-color, rgba(128,128,128,0.08)));display:flex;align-items:center;justify-content:center\"><ha-icon icon='mdi:cat' style='--mdc-icon-size:32px;color:${color}'></ha-icon></div>`; ]]]",
            "status_text": "[[[ " + state_map_js + " const st = entity.state; return `<span style=\"font-size:18px;font-weight:600;color:var(--md-sys-color-on-surface, var(--primary-text-color))\">${sm[st] || st}</span>`; ]]]",
            "detail_line": "[[[ " + event_map_js + " const ev = states['" + _litter_event + "'].state; const by = states['" + _litter_used_by + "'].state; return `<span style=\"font-size:13px;color:var(--md-sys-color-on-surface-variant, var(--secondary-text-color))\">${em[ev] || ev} · ${by}</span>`; ]]]",
            "alert_badges": "[[[ const sand = states['" + _litter_sand_lack + "'].state; const bin = states['" + _litter_bin_full + "'].state; const badges = []; if (sand === 'on') badges.push('<span style=\"background:var(--md-sys-color-error-container, #FDE7E9);color:var(--md-sys-color-on-error-container, #410E0B);padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600\">缺猫砂</span>'); if (bin === 'on') badges.push('<span style=\"background:var(--md-sys-color-tertiary-container, #FFE5C2);color:var(--md-sys-color-on-tertiary-container, #2F1500);padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600\">垃圾满</span>'); if (!badges.length) badges.push('<span style=\"background:var(--md-sys-color-secondary-container, #E8DEF8);color:var(--md-sys-color-on-secondary-container, #1D192B);padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600\">正常</span>'); return badges.join(' '); ]]]",
            "stats": "[[[ const wt = states['" + _litter_weight + "'].state; const lv = states['" + _litter_level + "'].state; const times = states['" + _litter_times + "'].state; const avg = states['" + _litter_avg + "'].state; const n50 = states['" + _litter_n50 + "'].state; return `<div style=\"display:flex;gap:12px;flex-wrap:wrap;font-size:13px;color:var(--md-sys-color-on-surface-variant, var(--secondary-text-color))\"><span>猫砂 ${wt}kg · ${lv}%</span><span>今日 ${times}次 · 均${avg}s</span><span>N50 ${n50}天</span></div>`; ]]]",
        },
        "styles": {
            "grid": [
                {"grid-template-areas": "'icon_area status_text alert_badges' 'icon_area detail_line alert_badges' 'stats stats stats'"},
                {"grid-template-columns": "52px 1fr auto"}, {"gap": "8px 12px"}, {"align-items": "start"},
            ],
            "card": [{"padding": "16px"}, {"border-radius": "28px"}, {"background": "var(--md-sys-color-surface-container, var(--ha-card-background))"}, {"box-shadow": "none !important"}, {"border": "none !important"}],
            "custom_fields": {
                "icon_area": [{"grid-area": "icon_area"}],
                "status_text": [{"grid-area": "status_text"}, {"align-self": "end"}],
                "detail_line": [{"grid-area": "detail_line"}, {"align-self": "start"}],
                "alert_badges": [{"grid-area": "alert_badges"}, {"justify-self": "end"}, {"align-self": "start"}],
                "stats": [{"grid-area": "stats"}, {"padding-top": "4px"}],
            },
        },
        "layout_options": {"grid_columns": 4},
        "card_mod": {"style": MD3_STYLE},
    }

def _action_btn(entity, label, icon):
    return md3_service_button(
        label,
        icon,
        "button.press",
        data={"entity_id": entity},
        confirmation_text=f"确定要{label}吗？",
        entity=entity,
        min_height="52px",
        font_size="14px",
        padding="8px 14px",
        radius="999px",
        grid_columns=2,
    )


pet_view = {
    "title": "宠物",
    "path": "pet",
    "icon": "mdi:paw",
    "type": "sections",
    "sections": [
        # --- Section 1: Nova ---
        section("", [
            pet_profile_pill_card(),
            mini_graph(
                [{"entity": _nova_weight, "name": "体重"}],
                name="体重趋势",
                hours_to_show=168,
                height=100,
                grid_columns=4,
            ),
        ]),

        # --- Section 2: 猫厕所MAX ---
        section("猫厕所", [
            litter_box_card(),
            _action_btn("button.zhi_neng_mao_ce_suo_max_scoop", "清理", "mdi:broom"),
            _action_btn("button.zhi_neng_mao_ce_suo_max_dump_litter", "倾空", "mdi:delete-empty"),
            _action_btn("button.zhi_neng_mao_ce_suo_max_level_litter", "抚平", "mdi:view-sequential"),
            _action_btn("button.zhi_neng_mao_ce_suo_max_maintenance_start", "进入维护", "mdi:wrench"),
            _action_btn("button.zhi_neng_mao_ce_suo_max_maintenance_exit", "退出维护", "mdi:wrench-check"),
            tile_toggle("switch.zhi_neng_mao_ce_suo_max_auto_clean", "自动清理", "mdi:autorenew"),
            tile_toggle("switch.zhi_neng_mao_ce_suo_max_power", "电源", "mdi:power"),
        ]),

        # --- Section 3: 饮水机MAX ---
        section("饮水机", [
            mushroom_template(
                "饮水机", "mdi:cup-water", "cyan",
                primary="饮水机MAX",
                secondary=(
                    "电量 {{ states('" + _fountain_battery + "') }}% · "
                    "滤芯 {{ states('" + _fountain_filter + "') }}% · "
                    "今日 {{ states('" + _fountain_drinks + "') }}次"
                ),
            ),
            mushroom_entity(_fountain_drinks, "饮水次数", "mdi:cup-water", "cyan"),
            mushroom_entity(_fountain_water, "累计净水 (mL)", "mdi:water", "blue"),
            mushroom_entity(_fountain_battery, "电池", "mdi:battery", "green"),
            mushroom_entity(_fountain_filter, "滤芯剩余", "mdi:filter", "amber"),
        ]),

        # --- Section 4: 喂食器 ---
        section("喂食器", [
            {
                "type": "custom:button-card",
                "entity": _feeder_food_level,
                "triggers_update": [_feeder_food_level, _feeder_desiccant, _feeder_daily_total, _feeder_feed_success],
                "show_icon": False, "show_name": False, "show_state": False,
                "custom_fields": {
                    "icon_area": "[[[ const lvl = entity.state; const color = lvl === 'Normal' ? 'var(--md-sys-color-on-surface-variant, var(--secondary-text-color))' : 'var(--md-sys-color-error, var(--error-color))'; return `<div style=\"width:52px;height:52px;border-radius:16px;background:var(--md-sys-color-surface-container-high, var(--secondary-background-color, rgba(128,128,128,0.08)));display:flex;align-items:center;justify-content:center\"><ha-icon icon='mdi:food-drumstick' style='--mdc-icon-size:32px;color:${color}'></ha-icon></div>`; ]]]",
                    "status_text": "[[[ const lm = {'Normal':'充足','Low':'偏低','Empty':'已空'}; return `<span style=\"font-size:18px;font-weight:600;color:var(--md-sys-color-on-surface, var(--primary-text-color))\">粮量 ${lm[entity.state] || entity.state}</span>`; ]]]",
                    "detail_line": "[[[ const dry = states['" + _feeder_desiccant + "'].state; return `<span style=\"font-size:13px;color:var(--md-sys-color-on-surface-variant, var(--secondary-text-color))\">干燥剂剩余 ${dry} 天</span>`; ]]]",
                    "alert_badges": "[[[ const lvl = entity.state; if (lvl === 'Empty') return '<span style=\"background:var(--md-sys-color-error-container, #FDE7E9);color:var(--md-sys-color-on-error-container, #410E0B);padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600\">已空</span>'; if (lvl === 'Low') return '<span style=\"background:var(--md-sys-color-tertiary-container, #FFE5C2);color:var(--md-sys-color-on-tertiary-container, #2F1500);padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600\">偏低</span>'; return '<span style=\"background:var(--md-sys-color-secondary-container, #E8DEF8);color:var(--md-sys-color-on-secondary-container, #1D192B);padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600\">正常</span>'; ]]]",
                    "stats": "[[[ const daily = states['" + _feeder_daily_total + "'].state; const ev = states['" + _feeder_feed_success + "']; const lastPortion = ev && ev.attributes && ev.attributes['实际出粮份数'] ? ev.attributes['实际出粮份数'] : '-'; return `<div style=\"display:flex;gap:12px;flex-wrap:wrap;font-size:13px;color:var(--md-sys-color-on-surface-variant, var(--secondary-text-color))\"><span>今日已出 ${daily || 0} 份</span><span>上次出粮 ${lastPortion} 份</span></div>`; ]]]",
                },
                "styles": {
                    "grid": [
                        {"grid-template-areas": "'icon_area status_text alert_badges' 'icon_area detail_line alert_badges' 'stats stats stats'"},
                        {"grid-template-columns": "52px 1fr auto"}, {"gap": "8px 12px"}, {"align-items": "start"},
                    ],
                    "card": [{"padding": "16px"}, {"border-radius": "28px"}, {"background": "var(--md-sys-color-surface-container, var(--ha-card-background))"}, {"box-shadow": "none !important"}, {"border": "none !important"}],
                    "custom_fields": {
                        "icon_area": [{"grid-area": "icon_area"}],
                        "status_text": [{"grid-area": "status_text"}, {"align-self": "end"}],
                        "detail_line": [{"grid-area": "detail_line"}, {"align-self": "start"}],
                        "alert_badges": [{"grid-area": "alert_badges"}, {"justify-self": "end"}, {"align-self": "start"}],
                        "stats": [{"grid-area": "stats"}, {"padding-top": "4px"}],
                    },
                },
                "layout_options": {"grid_columns": 4},
                "card_mod": {"style": MD3_STYLE},
            },
            mushroom_entity(_feeder_plan_unit, "每次出粮份数", "mdi:food-variant", "orange"),
            {
                "type": "custom:mushroom-template-card",
                "primary": "喂食计划",
                "secondary": "{{ '已开启' if states('" + _feeder_plan_ctrl + "') | int == 1 else '已关闭' }}",
                "icon": "mdi:calendar-clock",
                "icon_color": "{{ 'green' if states('" + _feeder_plan_ctrl + "') | int == 1 else 'disabled' }}",
                "tap_action": {
                    "action": "call-service",
                    "service": "script.pet_feeder_toggle_plan",
                },
                "card_mod": {"style": MD3_STYLE},
            },
            md3_service_button(
                "手动出粮",
                "mdi:shaker-outline",
                "script.pet_feeder_manual_feed",
                confirmation_text="确定要手动出粮吗？",
                min_height="52px",
                font_size="14px",
                padding="8px 14px",
                radius="999px",
                grid_columns=2,
            ),
            mushroom_entity(_feeder_daily_total, "今日出粮份数", "mdi:counter", "deep-orange"),
        ]),
    ],
}

laundry_view = {
    "title": "清洁",
    "path": "laundry",
    "icon": "mdi:washing-machine",
    "type": "sections",
    "sections": [
        section("🫧 洗衣机", [{"type": "conditional", "conditions": [{"entity": _washer_state, "state_not": "unavailable"}, {"entity": _washer_state, "state_not": "inactive"}, {"entity": _washer_state, "state_not": "off"}], "card": washer_button_card()}, {"type": "conditional", "conditions": [{"condition": "or", "conditions": [{"entity": _washer_state, "state": "inactive"}, {"entity": _washer_state, "state": "off"}, {"entity": _washer_state, "state": "unavailable"}]}], "card": mushroom_template("洗衣机", "mdi:washing-machine", "disabled", primary="洗衣机", secondary="已关机")}], columns=1),
        section("🔥 烘干机", [{"type": "conditional", "conditions": [{"entity": _dryer_state, "state_not": "unavailable"}, {"entity": _dryer_state, "state_not": "inactive"}, {"entity": _dryer_state, "state_not": "off"}], "card": dryer_button_card()}, {"type": "conditional", "conditions": [{"condition": "or", "conditions": [{"entity": _dryer_state, "state": "inactive"}, {"entity": _dryer_state, "state": "off"}, {"entity": _dryer_state, "state": "unavailable"}]}], "card": mushroom_template("烘干机", "mdi:tumble-dryer", "disabled", primary="烘干机", secondary="已关机")}], columns=1),
        section("🍽️ 洗碗机综合面板", [{"type": "conditional", "conditions": [{"entity": _dish_state, "state_not": "unavailable"}, {"entity": _dish_state, "state_not": "inactive"}, {"entity": _dish_state, "state_not": "off"}], "card": dishwasher_button_card()}, {"type": "conditional", "conditions": [{"condition": "or", "conditions": [{"entity": _dish_state, "state": "inactive"}, {"entity": _dish_state, "state": "off"}, {"entity": _dish_state, "state": "unavailable"}]}], "card": mushroom_template("洗碗机", "mdi:dishwasher", "disabled", primary="洗碗机", secondary="已关机")}])
    ]
}
views = [
    home_view,
    lighting_view,
    environment_view,
    climate_view,
    pet_view,
    laundry_view,
    misc_view,
]

# Apply global theme variables to each view
for v in views:
    v["card_mod"] = {"style": MD3_THEME_VARIABLES}

config = {
    "views": views
}

import websocket

if HA_URL.startswith("https://"):
    ws_base = "wss://" + HA_URL[len("https://"):]
elif HA_URL.startswith("http://"):
    ws_base = "ws://" + HA_URL[len("http://"):]
else:
    raise ValueError(f"Unsupported HA_URL scheme: {HA_URL}")

ws_url = ws_base + "/api/websocket"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
ws = websocket.create_connection(ws_url, timeout=15, sslopt={"cert_reqs": ssl.CERT_NONE})

# Step 1: Receive auth_required
msg = json.loads(ws.recv())
print(f"1. {msg['type']}")

# Step 2: Authenticate
ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
msg = json.loads(ws.recv())
print(f"2. {msg['type']}")
if msg["type"] != "auth_ok":
    print("Authentication failed!")
    ws.close()
    exit(1)

# Step 3: Save lovelace config
ws.send(json.dumps({
    "id": 1,
    "type": "lovelace/config/save",
    "config": config,
}))
msg = json.loads(ws.recv())
print(f"3. Result: success={msg.get('success')}")
if not msg.get("success"):
    print(f"   Error: {msg.get('error', {})}")

ws.close()
print("\nDashboard applied successfully!" if msg.get("success") else "\nFailed to apply dashboard.")
