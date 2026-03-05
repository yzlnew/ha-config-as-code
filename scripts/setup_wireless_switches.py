#!/usr/bin/env python3
"""Set all Xiaomi wall switches to wireless mode and bind buttons via event entities.

Wireless mode means switches no longer produce on/off state changes — instead each
button fires event entities (click, double_click, long_press). This script creates
29 automations covering click/double-click/long-press for all 14 switches.

Event entity pattern:
  event.xiaomi_cn_{id}_{type}_{action}_e_{svc}_{prop}

  w1: key  → svc=3, props 1/2/3 (click/double/long)
  w2: left → svc=4, right → svc=5
  w3: left → svc=5, middle → svc=6, right → svc=7
"""

import json
import ssl
import sys
import time

import websocket

from ha_api import (
    HA_URL, TOKEN, call_service, delete_automation, put_automation,
)


# ============================================================
# Wall switch definitions: device_id, type, name, area
# ============================================================
SWITCHES = [
    # 客厅
    {
        "id": "2000385088", "type": "w3", "name": "阳台柜开关", "area": "客厅",
        "mode_entities": [
            "select.xiaomi_cn_2000385088_w3_mode_p_2_2",
            "select.xiaomi_cn_2000385088_w3_mode_p_3_2",
            "select.xiaomi_cn_2000385088_w3_mode_p_4_2",
        ],
    },
    # 西厨
    {
        "id": "2000365940", "type": "w3", "name": "入口开关", "area": "西厨",
        "mode_entities": [
            "select.xiaomi_cn_2000365940_w3_mode_p_2_2",  # 左键
            "select.xiaomi_cn_2000365940_w3_mode_p_3_2",  # 中键
            "select.xiaomi_cn_2000365940_w3_mode_p_4_2",  # 右键
        ],
    },
    {
        "id": "2000345110", "type": "w3", "name": "厨房开关", "area": "厨房",
        "mode_entities": [
            "select.xiaomi_cn_2000345110_w3_mode_p_2_2",
            "select.xiaomi_cn_2000345110_w3_mode_p_3_2",
            "select.xiaomi_cn_2000345110_w3_mode_p_4_2",
        ],
    },
    # 主卧
    {
        "id": "2000414477", "type": "w3", "name": "小米智能开关（三开）", "area": "主卧",
        "mode_entities": [
            "select.xiaomi_cn_2000414477_w3_mode_p_2_2",
            "select.xiaomi_cn_2000414477_w3_mode_p_3_2",
            "select.xiaomi_cn_2000414477_w3_mode_p_4_2",
        ],
    },
    {
        "id": "2002248817", "type": "w1", "name": "右侧单开", "area": "主卧",
        "mode_entities": [
            "select.xiaomi_cn_2002248817_w1_mode_p_2_2",
        ],
    },
    {
        "id": "2021424385", "type": "w2", "name": "小米智能开关（双开） 6", "area": "主卧",
        "mode_entities": [
            "select.xiaomi_cn_2021424385_w2_mode_p_2_2",
            "select.xiaomi_cn_2021424385_w2_mode_p_3_2",
        ],
    },
    {
        "id": "2042152203", "type": "w2", "name": "小米智能开关（双开） 3", "area": "主卧",
        "mode_entities": [
            "select.xiaomi_cn_2042152203_w2_mode_p_2_2",
            "select.xiaomi_cn_2042152203_w2_mode_p_3_2",
        ],
    },
    # 次卧
    {
        "id": "2020906944", "type": "w1", "name": "小米智能开关（单开）", "area": "次卧",
        "mode_entities": [
            "select.xiaomi_cn_2020906944_w1_mode_p_2_2",
        ],
    },
    {
        "id": "2021427806", "type": "w2", "name": "小米智能开关（双开）", "area": "次卧",
        "mode_entities": [
            "select.xiaomi_cn_2021427806_w2_mode_p_2_2",
            "select.xiaomi_cn_2021427806_w2_mode_p_3_2",
        ],
    },
    {
        "id": "2022700953", "type": "w1", "name": "小米智能开关（单开） 2", "area": "次卧",
        "mode_entities": [
            "select.xiaomi_cn_2022700953_w1_mode_p_2_2",
        ],
    },
    {
        "id": "2022705523", "type": "w1", "name": "入口单开", "area": "次卧",
        "mode_entities": [
            "select.xiaomi_cn_2022705523_w1_mode_p_2_2",
        ],
    },
    # 主卫
    {
        "id": "2042094243", "type": "w2", "name": "小米智能开关（双开） 4", "area": "主卫",
        "mode_entities": [
            "select.xiaomi_cn_2042094243_w2_mode_p_2_2",
            "select.xiaomi_cn_2042094243_w2_mode_p_3_2",
        ],
    },
    # 次卫
    {
        "id": "2042194900", "type": "w2", "name": "小米智能开关（双开） 5", "area": "次卫",
        "mode_entities": [
            "select.xiaomi_cn_2042194900_w2_mode_p_2_2",
            "select.xiaomi_cn_2042194900_w2_mode_p_3_2",
        ],
    },
    # 书房
    {
        "id": "2021424647", "type": "w2", "name": "小米智能开关（双开） 2", "area": "书房",
        "mode_entities": [
            "select.xiaomi_cn_2021424647_w2_mode_p_2_2",
            "select.xiaomi_cn_2021424647_w2_mode_p_3_2",
        ],
    },
]

# ============================================================
# Area → light entities (spotlights/downlights)
# ============================================================
AREA_LIGHTS = {
    "客厅": [
        "light.intelligent_drive_power_supply_16",           # 泛光灯
        "light.intelligent_power",                           # 长格栅灯
        "light.intelligent_drive_power_supply_15",           # 格栅灯 1
        "light.intelligent_drive_power_supply_17",           # 格栅灯 2
        "light.intelligent_drive_power_supply_14",           # 格栅灯 3
        "light.intelligent_drive_power_supply_13",           # 折叠格栅灯
        "light.wlg_cn_949473222_wy0a06_s_2_light",          # 背景墙射灯 1
        "light.wlg_cn_949429122_wy0a06_s_2_light",          # 背景墙射灯 2
        "light.wlg_cn_949440999_wy0a06_s_2_light",          # 筒射灯 1
        "light.wlg_cn_949442390_wy0a06_s_2_light",          # 筒射灯 2
        "light.090615_cn_2000236373_milg05_s_2_light",       # 射灯 1
        "light.090615_cn_2000254702_milg05_s_2_light",       # 射灯 2
    ],
    "西厨": [
        "light.chu_fang_deng_guang",                         # 厨房灯光组（平板灯+射灯）
        "light.intelligent_drive_power_supply",              # 厨房入口射灯
        "light.intelligent_drive_power_supply_2",            # 背景墙
        "light.intelligent_drive_power_supply_3",            # 进门射灯
        "light.intelligent_drive_power_supply_4",            # Spotlight
        "light.wlg_cn_949413732_wy0a06_s_2_light",          # 筒射灯 1
        "light.wlg_cn_949433559_wy0a06_s_2_light",          # 筒射灯 2
        "light.wlg_cn_949433582_wy0a06_s_2_light",          # 筒射灯 3
        "light.wlg_cn_949435731_wy0a06_s_2_light",          # 筒射灯 4
    ],
    "厨房": [
        "light.intelligent_drive_power_supply_11",              # 平板灯
        "light.intelligent_drive_power_supply_12",              # 射灯
    ],
    "主卧": [
        "light.intelligent_drive_power_supply_22",           # 主灯
        "light.intelligent_drive_power_supply_20",           # 左射灯
        "light.intelligent_drive_power_supply_21",           # 右射灯
        "light.intelligent_drive_power_supply_18",           # 床头左射灯
        "light.intelligent_drive_power_supply_19",           # 床头右射灯
        "light.linp_cn_949882702_ld6bcw_s_2_light",         # 存在筒射灯
    ],
    "主卫": [
        "light.linp_cn_950194815_ld6bcw_s_2_light",         # 存在筒射灯
        "light.090615_cn_2000228017_milg05_s_2_light",       # 射灯 1
        "light.090615_cn_2000257106_milg05_s_2_light",       # 射灯 2
    ],
    "次卧": [
        "light.intelligent_drive_power_supply_5",            # 格栅灯
        "light.090615_cn_2000281237_milg05_s_2_light",       # 射灯 1
        "light.090615_cn_2000196741_milg05_s_2_light",       # 射灯 2
        "light.linp_cn_949847136_ld6bcw_s_2_light",         # 存在筒射灯
        "light.moes_matter_light",                           # 装饰灯
    ],
    "次卫": [
        "light.linp_cn_949833026_ld6bcw_s_2_light",         # 存在筒射灯
        "light.090615_cn_2000254608_milg05_s_2_light",       # 射灯 1
        "light.090615_cn_2000276840_milg05_s_2_light",       # 射灯 2
    ],
    "书房": [
        "light.intelligent_drive_power_supply_6",            # 主灯
        "light.intelligent_drive_power_supply_8",            # 射灯 1
        "light.intelligent_drive_power_supply_7",            # 射灯 2
        "light.intelligent_drive_power_supply_9",            # 射灯 3
        "light.intelligent_drive_power_supply_10",           # 射灯 4
        "light.lemesh_cn_2000705436_wy0d02_s_2_light",      # 色温灯
    ],
}

# Area → light strip entities
AREA_STRIPS = {
    "客厅": ["light.lemesh_cn_2023148762_wy0d02_s_2_light"],      # 背景墙灯带
    "西厨": [
        "light.lemesh_cn_2000921741_wy0d02_s_2_light",            # 岛台灯带
        "light.lemesh_cn_2023151493_wy0d02_s_2_light",            # 鞋柜灯带
    ],
    "主卧": [
        "light.lemesh_cn_2020771536_wy0d02_s_2_light",            # 床头灯带
        "light.lemesh_cn_2020803689_wy0d02_s_2_light",            # 入口灯带
    ],
    "次卧": ["light.lemesh_cn_2001035175_wy0d02_s_2_light"],      # 入口灯带
    "书房": ["light.lemesh_cn_2000705436_wy0d02_s_2_light"],      # 色温灯（兼灯带）
}

# Area → curtain entities
AREA_CURTAINS = {
    "客厅": [
        "cover.linp_cn_2079472416_ec1db_s_2_curtain",   # 布帘
        "cover.linp_cn_2079495198_ec1db_s_2_curtain",   # 纱帘
    ],
    "主卧": [
        "cover.bean_cn_1158897956_ct06_s_2_curtain",
    ],
    "次卧": [
        "cover.bean_cn_1158901062_ct06_s_2_curtain",
    ],
}

# Area → ventilation fan entity
AREA_VENT = {
    "主卫": "fan.xiaomi_cn_921633051_na2_s_3_fan",
    "次卫": "fan.xiaomi_cn_921633179_na2_s_3_fan",
}

# All lights for "full off" per area (main + strips + bath-specific)
AREA_ALL_LIGHTS = {}
for area in AREA_LIGHTS:
    AREA_ALL_LIGHTS[area] = list(AREA_LIGHTS[area])
    if area in AREA_STRIPS:
        # Avoid duplicates (书房 色温灯 is in both)
        for s in AREA_STRIPS[area]:
            if s not in AREA_ALL_LIGHTS[area]:
                AREA_ALL_LIGHTS[area].append(s)

# Add bath-specific lights not in AREA_LIGHTS for full-off
MASTER_BATH_EXTRA = ["light.xiaomi_cn_921633051_na2_s_2_light"]  # 浴霸灯
GUEST_BATH_EXTRA = ["light.yeelink_cn_945433772_v11_s_2_light"]  # 浴霸灯
for e in MASTER_BATH_EXTRA:
    if e not in AREA_ALL_LIGHTS["主卫"]:
        AREA_ALL_LIGHTS["主卫"].append(e)
for e in GUEST_BATH_EXTRA:
    if e not in AREA_ALL_LIGHTS["次卫"]:
        AREA_ALL_LIGHTS["次卫"].append(e)

AREA_ID_MAP = {
    "客厅": "living_room",
    "西厨": "west_kitchen",
    "厨房": "kitchen",
    "主卧": "master_bedroom",
    "次卧": "guest_bedroom",
    "主卫": "master_bath",
    "次卫": "guest_bath",
    "书房": "study",
}

# ============================================================
# Event entity helper
# ============================================================
# Event entity pattern: event.xiaomi_cn_{id}_{type}_{action}_e_{svc}_{prop}
# action: click / double_click / long_press
# svc/prop per type:
#   w1: key → svc=3, click=1/double=2/long=3
#   w2: left → svc=4, right → svc=5
#   w3: left → svc=5, middle → svc=6, right → svc=7

BUTTON_SVC = {
    "w1": {"key": 3},
    "w2": {"left": 4, "right": 5},
    "w3": {"left": 5, "middle": 6, "right": 7},
}

ACTION_PROP = {"click": 1, "double_click": 2, "long_press": 3}


def event_entity(sw_id, sw_type, button, action):
    """Build event entity_id for a switch button + action.

    button: "key", "left", "middle", "right"
    action: "click", "double_click", "long_press"
    """
    svc = BUTTON_SVC[sw_type][button]
    prop = ACTION_PROP[action]
    return f"event.xiaomi_cn_{sw_id}_{sw_type}_{action}_e_{svc}_{prop}"


def left_button(sw):
    """Return the 'left' button name for a switch type."""
    return "key" if sw["type"] == "w1" else "left"


# Group switches by area
area_switches = {}
for sw in SWITCHES:
    area_switches.setdefault(sw["area"], []).append(sw)


# ============================================================
# Helper: build toggle action using choose template
# ============================================================
def make_toggle_action(lights):
    """Smart toggle: if any light is on → all off; else all on."""
    lights_str = ", ".join(f"'{e}'" for e in lights)
    return [
        {
            "choose": [
                {
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": (
                                "{{ expand([" + lights_str + "]) "
                                "| selectattr('state','eq','on') | list | count > 0 }}"
                            ),
                        }
                    ],
                    "sequence": [
                        {"service": "light.turn_off", "target": {"entity_id": lights}},
                    ],
                }
            ],
            "default": [
                {"service": "light.turn_on", "target": {"entity_id": lights}},
            ],
        }
    ]


def make_curtain_toggle_action(curtains):
    """Toggle curtains: if any open → close all; else open all."""
    curtains_str = ", ".join(f"'{e}'" for e in curtains)
    return [
        {
            "choose": [
                {
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": (
                                "{{ expand([" + curtains_str + "]) "
                                "| selectattr('state','eq','open') | list | count > 0 }}"
                            ),
                        }
                    ],
                    "sequence": [
                        {"service": "cover.close_cover", "target": {"entity_id": curtains}},
                    ],
                }
            ],
            "default": [
                {"service": "cover.open_cover", "target": {"entity_id": curtains}},
            ],
        }
    ]


def make_vent_toggle_action(vent_entity):
    """Toggle ventilation fan."""
    return [{"service": "fan.toggle", "target": {"entity_id": vent_entity}}]


def make_full_off_action(area):
    """Turn off all lights in area + curtains/vent if applicable."""
    actions = [
        {"service": "light.turn_off", "target": {"entity_id": AREA_ALL_LIGHTS[area]}},
    ]
    return actions


# ============================================================
# Old automation IDs to clean up
# ============================================================
OLD_AUTOMATION_IDS = [
    # Old on/off pairs from setup_wireless_switches.py
    "switch_living_room_lights_on",
    "switch_living_room_lights_off",
    "switch_west_kitchen_lights_on",
    "switch_west_kitchen_lights_off",
    "switch_master_bedroom_lights_on",
    "switch_master_bedroom_lights_off",
    "switch_guest_bedroom_lights_on",
    "switch_guest_bedroom_lights_off",
    "switch_master_bathroom_lights_on",
    "switch_master_bathroom_lights_off",
    "switch_guest_bathroom_lights_on",
    "switch_guest_bathroom_lights_off",
    "switch_study_lights_on",
    "switch_study_lights_off",
    # Old scene automations from setup_scenes.py
    "scene_guest_on",
    "scene_guest_off",
    "scene_cinema_on",
    "scene_cinema_off",
    "scene_sleep_on",
    "scene_sleep_off",
]

# ============================================================
# Display name/icon by unique_id (for entity registry)
# ============================================================
DISPLAY_BY_UNIQUE_ID = {
    "btn_living_room_left_click": {
        "name": "开关绑定：客厅灯光切换", "icon": "mdi:light-switch",
        "desired_entity_id": "automation.btn_living_room_left_click",
    },
    "btn_living_room_left_dblclick": {
        "name": "开关绑定：客厅灯带切换", "icon": "mdi:led-strip-variant",
        "desired_entity_id": "automation.btn_living_room_left_dblclick",
    },
    "btn_living_room_left_longpress": {
        "name": "开关绑定：客厅全关", "icon": "mdi:light-switch-off",
        "desired_entity_id": "automation.btn_living_room_left_longpress",
    },
    "btn_living_room_middle_click": {
        "name": "开关绑定：会客模式", "icon": "mdi:account-group",
        "desired_entity_id": "automation.btn_living_room_middle_click",
    },
    "btn_living_room_right_click": {
        "name": "开关绑定：影音模式", "icon": "mdi:movie-open",
        "desired_entity_id": "automation.btn_living_room_right_click",
    },
    "btn_living_room_right_dblclick": {
        "name": "开关绑定：阳台窗帘切换", "icon": "mdi:curtains",
        "desired_entity_id": "automation.btn_living_room_right_dblclick",
    },
    "btn_west_kitchen_left_click": {
        "name": "开关绑定：西厨灯光切换", "icon": "mdi:light-switch",
        "desired_entity_id": "automation.btn_west_kitchen_left_click",
    },
    "btn_west_kitchen_left_dblclick": {
        "name": "开关绑定：西厨灯带切换", "icon": "mdi:led-strip-variant",
        "desired_entity_id": "automation.btn_west_kitchen_left_dblclick",
    },
    "btn_west_kitchen_left_longpress": {
        "name": "开关绑定：全屋关灯", "icon": "mdi:home-lightbulb-outline",
        "desired_entity_id": "automation.btn_west_kitchen_left_longpress",
    },
    "btn_west_kitchen_middle_click": {
        "name": "开关绑定：会客模式", "icon": "mdi:account-group",
        "desired_entity_id": "automation.btn_west_kitchen_middle_click",
    },
    "btn_west_kitchen_right_click": {
        "name": "开关绑定：影音模式", "icon": "mdi:movie-open",
        "desired_entity_id": "automation.btn_west_kitchen_right_click",
    },
    "btn_kitchen_left_click": {
        "name": "开关绑定：厨房灯光切换", "icon": "mdi:light-switch",
        "desired_entity_id": "automation.btn_kitchen_left_click",
    },
    "btn_kitchen_left_dblclick": {
        "name": "开关绑定：西厨灯光切换（厨房）", "icon": "mdi:light-switch",
        "desired_entity_id": "automation.btn_kitchen_left_dblclick",
    },
    "btn_kitchen_left_longpress": {
        "name": "开关绑定：厨房全关", "icon": "mdi:light-switch-off",
        "desired_entity_id": "automation.btn_kitchen_left_longpress",
    },
    "btn_kitchen_middle_click": {
        "name": "开关绑定：厨房亮度+", "icon": "mdi:brightness-7",
        "desired_entity_id": "automation.btn_kitchen_middle_click",
    },
    "btn_kitchen_middle_dblclick": {
        "name": "开关绑定：厨房亮度-", "icon": "mdi:brightness-5",
        "desired_entity_id": "automation.btn_kitchen_middle_dblclick",
    },
    "btn_kitchen_middle_longpress": {
        "name": "开关绑定：厨房重置自适应", "icon": "mdi:refresh",
        "desired_entity_id": "automation.btn_kitchen_middle_longpress",
    },
    "btn_kitchen_right_click": {
        "name": "开关绑定：厨房色温+暖", "icon": "mdi:sun-thermometer",
        "desired_entity_id": "automation.btn_kitchen_right_click",
    },
    "btn_kitchen_right_dblclick": {
        "name": "开关绑定：厨房色温-冷", "icon": "mdi:snowflake-thermometer",
        "desired_entity_id": "automation.btn_kitchen_right_dblclick",
    },
    "btn_kitchen_right_longpress": {
        "name": "开关绑定：厨房重置自适应", "icon": "mdi:refresh",
        "desired_entity_id": "automation.btn_kitchen_right_longpress",
    },
    "btn_master_bedroom_left_click": {
        "name": "开关绑定：主卧灯光切换", "icon": "mdi:light-switch",
        "desired_entity_id": "automation.btn_master_bedroom_left_click",
    },
    "btn_master_bedroom_left_dblclick": {
        "name": "开关绑定：主卧灯带切换", "icon": "mdi:led-strip-variant",
        "desired_entity_id": "automation.btn_master_bedroom_left_dblclick",
    },
    "btn_master_bedroom_left_longpress": {
        "name": "开关绑定：主卧全关", "icon": "mdi:light-switch-off",
        "desired_entity_id": "automation.btn_master_bedroom_left_longpress",
    },
    "btn_master_bedroom_middle_click": {
        "name": "开关绑定：睡眠模式", "icon": "mdi:weather-night",
        "desired_entity_id": "automation.btn_master_bedroom_middle_click",
    },
    "btn_master_bedroom_right_click": {
        "name": "开关绑定：主卧窗帘切换", "icon": "mdi:curtains",
        "desired_entity_id": "automation.btn_master_bedroom_right_click",
    },
    "btn_guest_bedroom_left_click": {
        "name": "开关绑定：次卧灯光切换", "icon": "mdi:light-switch",
        "desired_entity_id": "automation.btn_guest_bedroom_left_click",
    },
    "btn_guest_bedroom_left_dblclick": {
        "name": "开关绑定：次卧灯带切换", "icon": "mdi:led-strip-variant",
        "desired_entity_id": "automation.btn_guest_bedroom_left_dblclick",
    },
    "btn_guest_bedroom_right_click": {
        "name": "开关绑定：次卧窗帘切换", "icon": "mdi:curtains",
        "desired_entity_id": "automation.btn_guest_bedroom_right_click",
    },
    "btn_guest_bedroom_left_longpress": {
        "name": "开关绑定：次卧全关", "icon": "mdi:light-switch-off",
        "desired_entity_id": "automation.btn_guest_bedroom_left_longpress",
    },
    "btn_master_bath_left_click": {
        "name": "开关绑定：主卫灯光切换", "icon": "mdi:light-switch",
        "desired_entity_id": "automation.btn_master_bath_left_click",
    },
    "btn_master_bath_left_longpress": {
        "name": "开关绑定：主卫全关", "icon": "mdi:light-switch-off",
        "desired_entity_id": "automation.btn_master_bath_left_longpress",
    },
    "btn_master_bath_right_click": {
        "name": "开关绑定：主卫换气切换", "icon": "mdi:fan",
        "desired_entity_id": "automation.btn_master_bath_right_click",
    },
    "btn_guest_bath_left_click": {
        "name": "开关绑定：次卫灯光切换", "icon": "mdi:light-switch",
        "desired_entity_id": "automation.btn_guest_bath_left_click",
    },
    "btn_guest_bath_left_longpress": {
        "name": "开关绑定：次卫全关", "icon": "mdi:light-switch-off",
        "desired_entity_id": "automation.btn_guest_bath_left_longpress",
    },
    "btn_guest_bath_right_click": {
        "name": "开关绑定：次卫换气切换", "icon": "mdi:fan",
        "desired_entity_id": "automation.btn_guest_bath_right_click",
    },
    "btn_study_left_click": {
        "name": "开关绑定：书房灯光切换", "icon": "mdi:light-switch",
        "desired_entity_id": "automation.btn_study_left_click",
    },
    "btn_study_left_dblclick": {
        "name": "开关绑定：书房灯带切换", "icon": "mdi:led-strip-variant",
        "desired_entity_id": "automation.btn_study_left_dblclick",
    },
    "btn_study_left_longpress": {
        "name": "开关绑定：书房全关", "icon": "mdi:light-switch-off",
        "desired_entity_id": "automation.btn_study_left_longpress",
    },
}


# ============================================================
# Build automation definitions
# ============================================================

def triggers_for(switches, button, action):
    """Build trigger list for given switches, button, and action."""
    triggers = []
    for sw in switches:
        btn = button if button != "left" else left_button(sw)
        # Skip if this switch type doesn't have this button
        if btn not in BUTTON_SVC.get(sw["type"], {}):
            continue
        triggers.append({
            "platform": "state",
            "entity_id": event_entity(sw["id"], sw["type"], btn, action),
            "not_from": ["unavailable", "unknown"],
            "not_to": ["unavailable", "unknown"],
        })
    return triggers


AUTOMATIONS = []


def add_auto(auto_id, alias, description, triggers, action):
    """Register an automation definition."""
    AUTOMATIONS.append({
        "id": auto_id,
        "config": {
            "alias": alias,
            "description": description,
            "trigger": triggers,
            "condition": [],
            "action": action,
            "mode": "single",
        },
    })


# --- 客厅 ---
lr_switches = area_switches["客厅"]

add_auto("btn_living_room_left_click",
         "Btn: Living Room Light Toggle",
         "Living room left/key click -> toggle lights",
         triggers_for(lr_switches, "left", "click"),
         make_toggle_action(AREA_LIGHTS["客厅"]))

add_auto("btn_living_room_left_dblclick",
         "Btn: Living Room Strip Toggle",
         "Living room left/key double-click -> toggle strip",
         triggers_for(lr_switches, "left", "double_click"),
         make_toggle_action(AREA_STRIPS["客厅"]))

add_auto("btn_living_room_left_longpress",
         "Btn: Living Room All Off",
         "Living room left/key long-press -> all lights off",
         triggers_for(lr_switches, "left", "long_press"),
         make_full_off_action("客厅"))

add_auto("btn_living_room_middle_click",
         "Btn: Living Room Guest Scene",
         "Living room middle click -> activate guest scene",
         triggers_for(lr_switches, "middle", "click"),
         [{"service": "scene.turn_on", "target": {"entity_id": "scene.hui_ke_mo_shi"}}])

add_auto("btn_living_room_right_click",
         "Btn: Living Room Cinema Scene",
         "Living room right click -> activate cinema scene",
         triggers_for(lr_switches, "right", "click"),
         [{"service": "scene.turn_on", "target": {"entity_id": "scene.ying_yin_mo_shi"}}])

add_auto("btn_living_room_right_dblclick",
         "Btn: Living Room Curtain Toggle",
         "Living room right double-click -> toggle balcony curtains",
         triggers_for(lr_switches, "right", "double_click"),
         make_curtain_toggle_action(AREA_CURTAINS["客厅"]))

# --- 西厨 ---
wk_switches = area_switches["西厨"]

add_auto("btn_west_kitchen_left_click",
         "Btn: West Kitchen Light Toggle",
         "West kitchen left click -> toggle west kitchen lights",
         triggers_for(wk_switches, "left", "click"),
         make_toggle_action(AREA_LIGHTS["西厨"]))

add_auto("btn_west_kitchen_left_dblclick",
         "Btn: West Kitchen Strip Toggle",
         "West kitchen left double-click -> toggle strips",
         triggers_for(wk_switches, "left", "double_click"),
         make_toggle_action(AREA_STRIPS["西厨"]))

all_off_lights = []
for _al in AREA_ALL_LIGHTS.values():
    all_off_lights.extend(_al)
all_off_lights = list(dict.fromkeys(all_off_lights))  # dedupe, preserve order

add_auto("btn_west_kitchen_left_longpress",
         "Btn: West Kitchen All Off (Whole House)",
         "West kitchen left long-press -> all lights off (whole house)",
         triggers_for(wk_switches, "left", "long_press"),
         [{"service": "light.turn_off", "target": {"entity_id": all_off_lights}}])

add_auto("btn_west_kitchen_middle_click",
         "Btn: West Kitchen Guest Scene",
         "West kitchen middle click -> activate guest scene",
         triggers_for(wk_switches, "middle", "click"),
         [{"service": "scene.turn_on", "target": {"entity_id": "scene.hui_ke_mo_shi"}}])

add_auto("btn_west_kitchen_right_click",
         "Btn: West Kitchen Cinema Scene",
         "West kitchen right click -> activate cinema scene",
         triggers_for(wk_switches, "right", "click"),
         [{"service": "scene.turn_on", "target": {"entity_id": "scene.ying_yin_mo_shi"}}])

# --- 厨房 ---
k_switches = area_switches["厨房"]
_k_lights = AREA_LIGHTS["厨房"]
_k_ref_light = _k_lights[0]  # reference light for reading current state
_k_al_switch = "switch.adaptive_lighting_chu_fang"
BRIGHTNESS_STEP = 20  # percent
COLOR_TEMP_STEP = 500  # kelvin
COLOR_TEMP_MIN = 2000
COLOR_TEMP_MAX = 6500

add_auto("btn_kitchen_left_click",
         "Btn: Kitchen Light Toggle",
         "Kitchen left click -> toggle kitchen lights",
         triggers_for(k_switches, "left", "click"),
         make_toggle_action(_k_lights))

add_auto("btn_kitchen_left_dblclick",
         "Btn: Kitchen West Kitchen Toggle",
         "Kitchen left double-click -> toggle west kitchen lights",
         triggers_for(k_switches, "left", "double_click"),
         make_toggle_action(AREA_LIGHTS["西厨"]))

add_auto("btn_kitchen_left_longpress",
         "Btn: Kitchen All Off",
         "Kitchen left long-press -> all kitchen lights off",
         triggers_for(k_switches, "left", "long_press"),
         make_full_off_action("厨房"))

add_auto("btn_kitchen_middle_click",
         "Btn: Kitchen Brightness Up",
         "Kitchen middle click -> brightness up",
         triggers_for(k_switches, "middle", "click"),
         [{"service": "light.turn_on", "target": {"entity_id": _k_lights},
           "data": {"brightness_step_pct": BRIGHTNESS_STEP}}])

add_auto("btn_kitchen_middle_dblclick",
         "Btn: Kitchen Brightness Down",
         "Kitchen middle double-click -> brightness down",
         triggers_for(k_switches, "middle", "double_click"),
         [{"service": "light.turn_on", "target": {"entity_id": _k_lights},
           "data": {"brightness_step_pct": -BRIGHTNESS_STEP}}])

add_auto("btn_kitchen_middle_longpress",
         "Btn: Kitchen Reset Adaptive (Mid)",
         "Kitchen middle long-press -> reset to adaptive lighting",
         triggers_for(k_switches, "middle", "long_press"),
         [{"service": "adaptive_lighting.set_manual_control",
           "data": {"entity_id": _k_al_switch, "manual_control": False,
                    "lights": _k_lights}}])

add_auto("btn_kitchen_right_click",
         "Btn: Kitchen Color Temp Warmer",
         "Kitchen right click -> color temp warmer (+500K)",
         triggers_for(k_switches, "right", "click"),
         [{"service": "light.turn_on", "target": {"entity_id": _k_lights},
           "data": {"color_temp_kelvin":
                    "{{ [[state_attr('" + _k_ref_light + "', 'color_temp_kelvin')"
                    " | int(" + str((COLOR_TEMP_MIN + COLOR_TEMP_MAX) // 2) + ")"
                    " + " + str(COLOR_TEMP_STEP) + ", "
                    + str(COLOR_TEMP_MIN) + "] | max, "
                    + str(COLOR_TEMP_MAX) + "] | min }}"}}])

add_auto("btn_kitchen_right_dblclick",
         "Btn: Kitchen Color Temp Cooler",
         "Kitchen right double-click -> color temp cooler (-500K)",
         triggers_for(k_switches, "right", "double_click"),
         [{"service": "light.turn_on", "target": {"entity_id": _k_lights},
           "data": {"color_temp_kelvin":
                    "{{ [[state_attr('" + _k_ref_light + "', 'color_temp_kelvin')"
                    " | int(" + str((COLOR_TEMP_MIN + COLOR_TEMP_MAX) // 2) + ")"
                    " - " + str(COLOR_TEMP_STEP) + ", "
                    + str(COLOR_TEMP_MIN) + "] | max, "
                    + str(COLOR_TEMP_MAX) + "] | min }}"}}])

add_auto("btn_kitchen_right_longpress",
         "Btn: Kitchen Reset Adaptive (Right)",
         "Kitchen right long-press -> reset to adaptive lighting",
         triggers_for(k_switches, "right", "long_press"),
         [{"service": "adaptive_lighting.set_manual_control",
           "data": {"entity_id": _k_al_switch, "manual_control": False,
                    "lights": _k_lights}}])

# --- 主卧 ---
mb_switches = area_switches["主卧"]
mb_w3 = [sw for sw in mb_switches if sw["type"] == "w3"]
# Right button: w3 + w2 (all except w1)
mb_right_switches = [sw for sw in mb_switches if sw["type"] != "w1"]

add_auto("btn_master_bedroom_left_click",
         "Btn: Master Bedroom Light Toggle",
         "Master bedroom left/key click -> toggle lights",
         triggers_for(mb_switches, "left", "click"),
         make_toggle_action(AREA_LIGHTS["主卧"]))

add_auto("btn_master_bedroom_left_dblclick",
         "Btn: Master Bedroom Strip Toggle",
         "Master bedroom left/key double-click -> toggle strips",
         triggers_for(mb_switches, "left", "double_click"),
         make_toggle_action(AREA_STRIPS["主卧"]))

add_auto("btn_master_bedroom_left_longpress",
         "Btn: Master Bedroom All Off",
         "Master bedroom left/key long-press -> all lights off",
         triggers_for(mb_switches, "left", "long_press"),
         make_full_off_action("主卧"))

add_auto("btn_master_bedroom_middle_click",
         "Btn: Master Bedroom Sleep Scene",
         "Master bedroom middle click -> activate sleep scene",
         triggers_for(mb_w3, "middle", "click"),
         [{"service": "scene.turn_on", "target": {"entity_id": "scene.shui_mian_mo_shi"}}])

add_auto("btn_master_bedroom_right_click",
         "Btn: Master Bedroom Curtain Toggle",
         "Master bedroom right click -> toggle curtains",
         triggers_for(mb_right_switches, "right", "click"),
         make_curtain_toggle_action(AREA_CURTAINS["主卧"]))

# --- 次卧 ---
gb_switches = area_switches["次卧"]

add_auto("btn_guest_bedroom_left_click",
         "Btn: Guest Bedroom Light Toggle",
         "Guest bedroom left/key click -> toggle lights",
         triggers_for(gb_switches, "left", "click"),
         make_toggle_action(AREA_LIGHTS["次卧"]))

add_auto("btn_guest_bedroom_left_dblclick",
         "Btn: Guest Bedroom Strip Toggle",
         "Guest bedroom left/key double-click -> toggle strip",
         triggers_for(gb_switches, "left", "double_click"),
         make_toggle_action(AREA_STRIPS["次卧"]))

add_auto("btn_guest_bedroom_right_click",
         "Btn: Guest Bedroom Curtain Toggle",
         "Guest bedroom right click -> toggle curtains",
         triggers_for(gb_switches, "right", "click"),
         make_curtain_toggle_action(AREA_CURTAINS["次卧"]))

add_auto("btn_guest_bedroom_left_longpress",
         "Btn: Guest Bedroom All Off",
         "Guest bedroom left/key long-press -> all lights off",
         triggers_for(gb_switches, "left", "long_press"),
         make_full_off_action("次卧"))

# --- 主卫 ---
mbath_switches = area_switches["主卫"]

add_auto("btn_master_bath_left_click",
         "Btn: Master Bath Light Toggle",
         "Master bath left click -> toggle lights",
         triggers_for(mbath_switches, "left", "click"),
         make_toggle_action(AREA_LIGHTS["主卫"]))

add_auto("btn_master_bath_left_longpress",
         "Btn: Master Bath All Off",
         "Master bath left long-press -> all lights off",
         triggers_for(mbath_switches, "left", "long_press"),
         make_full_off_action("主卫"))

add_auto("btn_master_bath_right_click",
         "Btn: Master Bath Vent Toggle",
         "Master bath right click -> toggle ventilation fan",
         triggers_for(mbath_switches, "right", "click"),
         make_vent_toggle_action(AREA_VENT["主卫"]))

# --- 次卫 ---
gbath_switches = area_switches["次卫"]

add_auto("btn_guest_bath_left_click",
         "Btn: Guest Bath Light Toggle",
         "Guest bath left click -> toggle lights",
         triggers_for(gbath_switches, "left", "click"),
         make_toggle_action(AREA_LIGHTS["次卫"]))

add_auto("btn_guest_bath_left_longpress",
         "Btn: Guest Bath All Off",
         "Guest bath left long-press -> all lights off",
         triggers_for(gbath_switches, "left", "long_press"),
         make_full_off_action("次卫"))

add_auto("btn_guest_bath_right_click",
         "Btn: Guest Bath Vent Toggle",
         "Guest bath right click -> toggle ventilation fan",
         triggers_for(gbath_switches, "right", "click"),
         make_vent_toggle_action(AREA_VENT["次卫"]))

# --- 书房 ---
st_switches = area_switches["书房"]

add_auto("btn_study_left_click",
         "Btn: Study Light Toggle",
         "Study left click -> toggle lights",
         triggers_for(st_switches, "left", "click"),
         make_toggle_action(AREA_LIGHTS["书房"]))

add_auto("btn_study_left_dblclick",
         "Btn: Study Strip Toggle",
         "Study left double-click -> toggle strip",
         triggers_for(st_switches, "left", "double_click"),
         make_toggle_action(AREA_STRIPS["书房"]))

add_auto("btn_study_left_longpress",
         "Btn: Study All Off",
         "Study left long-press -> all lights off",
         triggers_for(st_switches, "left", "long_press"),
         make_full_off_action("书房"))


# ============================================================
# Step 1: Set all buttons to wireless mode (无线开关)
# Only runs with --set-wireless flag (slow, only needed once)
# ============================================================
if "--set-wireless" in sys.argv:
    print("=" * 60)
    print("Step 1: Setting all buttons to wireless mode")
    print("=" * 60)

    for sw in SWITCHES:
        print(f"\n[{sw['area']}] {sw['name']} ({sw['type']})")
        for mode_entity in sw["mode_entities"]:
            try:
                call_service("select", "select_option", {
                    "entity_id": mode_entity,
                    "option": "无线开关",
                })
                print(f"  -> {mode_entity} -> wireless")
            except Exception as e:
                print(f"  !! {mode_entity} -> {e}")
            time.sleep(0.3)
else:
    print("Step 1: SKIPPED (pass --set-wireless to run)")

# ============================================================
# Step 2: Delete old automations
# Only runs with --cleanup flag
# ============================================================
if "--cleanup" in sys.argv:
    print("\n" + "=" * 60)
    print("Step 2: Deleting old automations")
    print("=" * 60)

    for old_id in OLD_AUTOMATION_IDS:
        delete_automation(old_id)

    print("\nReloading automations...")
    try:
        call_service("automation", "reload", {})
        print("Automations reloaded!")
    except Exception as e:
        print(f"Reload failed: {e}")
else:
    print("Step 2: SKIPPED (pass --cleanup to run)")

# ============================================================
# Step 3: Create event-based button automations
# Only runs with --bind flag
# ============================================================
if "--bind" in sys.argv:
    print("\n" + "=" * 60)
    print(f"Step 3: Creating {len(AUTOMATIONS)} button automations")
    print("=" * 60)

    for auto in AUTOMATIONS:
        put_automation(auto["id"], auto["config"])

    # Reload automations
    print("\nReloading automations...")
    try:
        call_service("automation", "reload", {})
        print("Automations reloaded!")
    except Exception as e:
        print(f"Reload failed: {e}")

    # ============================================================
    # Step 4: Set Chinese display names & icons via entity registry
    # ============================================================
    print("\n" + "=" * 60)
    print("Step 4: Setting Chinese display names & icons")
    print("=" * 60)

    time.sleep(2)

    ws_url = HA_URL.replace("https://", "wss://") + "/api/websocket"
    ws = websocket.create_connection(ws_url, sslopt={"cert_reqs": ssl.CERT_NONE})

    msg = json.loads(ws.recv())
    ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
    msg = json.loads(ws.recv())
    assert msg["type"] == "auth_ok", f"Auth failed: {msg}"

    # Build unique_id -> actual entity_id map from registry
    ws.send(json.dumps({"id": 999, "type": "config/entity_registry/list"}))
    registry = json.loads(ws.recv())
    uid_to_eid = {e["unique_id"]: e["entity_id"] for e in registry.get("result", [])}

    msg_id = 1000
    for unique_id, display in DISPLAY_BY_UNIQUE_ID.items():
        actual_eid = uid_to_eid.get(unique_id)
        if not actual_eid:
            print(f"  [SKIP] unique_id={unique_id} not found in registry")
            continue

        desired_eid = display["desired_entity_id"]

        # Rename entity_id if it doesn't match desired (e.g. has _2 suffix)
        if actual_eid != desired_eid:
            ws.send(json.dumps({
                "id": msg_id,
                "type": "config/entity_registry/update",
                "entity_id": actual_eid,
                "new_entity_id": desired_eid,
            }))
            result = json.loads(ws.recv())
            if result.get("success"):
                print(f"  [RENAME] {actual_eid} -> {desired_eid}")
                actual_eid = desired_eid
            else:
                print(f"  [RENAME FAIL] {actual_eid}: {result.get('error', {}).get('message', '?')}")
            msg_id += 1

        # Set display name and icon
        ws.send(json.dumps({
            "id": msg_id,
            "type": "config/entity_registry/update",
            "entity_id": actual_eid,
            "name": display["name"],
            "icon": display["icon"],
        }))
        result = json.loads(ws.recv())
        status = "OK" if result.get("success") else f"FAIL: {result.get('error', {}).get('message', '?')}"
        print(f"  [{status}] {actual_eid} -> {display['name']}")
        msg_id += 1

    ws.close()
else:
    print("Step 3: SKIPPED (pass --bind to run)")

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 60)
print("Done!")
print("=" * 60)
if "--set-wireless" not in sys.argv and "--bind" not in sys.argv and "--cleanup" not in sys.argv:
    print("  Nothing to do. Available flags:")
    print("    --set-wireless  Set all buttons to wireless mode")
    print("    --cleanup       Delete old on/off automations")
    print("    --bind          Create event-based button automations")
