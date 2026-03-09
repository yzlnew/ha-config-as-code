#!/usr/bin/env python3
"""Centralized Automation Management: Organizes automations by logical groups."""

import json
import ssl
import time

import websocket

from ha_api import HA_URL, TOKEN, api, put_automation, call_service

# ============================================================
# Automation Definitions
# ============================================================
automations = {}

# Note: Physical Switch Bindings (会客/影音/睡眠) are managed by setup_scenes.py
# which handles both ON and OFF directions. Do not duplicate here.

# --- Group 1: Environment & Climate ---
automations["bath_dehumidification_on"] = {
    "alias": "环境自动：主卫除湿开启",

    "trigger": [
        {"platform": "numeric_state", "entity_id": "sensor.xiaomi_cn_921633051_na2_relative_humidity_p_11_9", "above": 65},
        {"platform": "state", "entity_id": "binary_sensor.linp_cn_1139276665_hb01_occupancy_status_p_2_1", "from": "off", "to": "on"}
    ],
    "condition": [
        {"condition": "numeric_state", "entity_id": "sensor.xiaomi_cn_921633051_na2_relative_humidity_p_11_9", "above": 65},
        {"condition": "state", "entity_id": "binary_sensor.linp_cn_1139276665_hb01_occupancy_status_p_2_1", "state": "on"}
    ],
    "action": [{"service": "switch.turn_on", "target": {"entity_id": "switch.xiaomi_cn_921633051_na2_ventilation_p_4_8"}}],
    "mode": "single"
}

automations["bath_dehumidification_off"] = {
    "alias": "环境自动：主卫除湿关闭",

    "trigger": [{"platform": "numeric_state", "entity_id": "sensor.xiaomi_cn_921633051_na2_relative_humidity_p_11_9", "below": 50}],
    "action": [{"service": "switch.turn_off", "target": {"entity_id": "switch.xiaomi_cn_921633051_na2_ventilation_p_4_8"}}],
    "mode": "single"
}

# --- Group 3: Leave & Welcome Home ---
# leave_home_guard is managed by create_leave_home_automation.py (input_boolean-based version)

automations["welcome_home_mode"] = {
    "alias": "安全守护：欢迎回家",

    "trigger": [
        {"platform": "state", "entity_id": "input_boolean.zai_jia_que_ren", "from": "off", "to": "on"},
        {"platform": "state", "entity_id": "event.lumi_cn_1011935590_bzacn1_lock_opened_e_2_1"},
    ],
    "condition": [{"condition": "numeric_state", "entity_id": "sensor.linp_cn_949882702_ld6bcw_illumination_p_5_5", "below": 10}],
    "action": [{"service": "light.turn_on", "target": {"entity_id": [
        "light.xi_chu_deng_guang",
        "light.ke_ting_dian_shi_gui_dao",
        "light.ke_ting_sha_fa_gui_dao",
        "light.ke_ting_zhuo_zi_gui_dao",
    ]}}],
    "mode": "single"
}

# --- Group 3b: Toilet Exhaust Fan ---
automations["toilet_exhaust_on"] = {
    "alias": "环境自动：马桶坐人开排风",

    "trigger": [{"platform": "state", "entity_id": "binary_sensor.zhimi_cn_873345887_pa6_seating_state_p_2_5", "from": "off", "to": "on"}],
    "action": [{"service": "switch.turn_on", "target": {"entity_id": "switch.xiaomi_cn_921633051_na2_ventilation_p_4_8"}}],
    "mode": "single"
}

automations["toilet_exhaust_off"] = {
    "alias": "环境自动：马桶离座延时关排风",

    "trigger": [{"platform": "state", "entity_id": "binary_sensor.zhimi_cn_873345887_pa6_seating_state_p_2_5", "from": "on", "to": "off", "for": {"minutes": 2}}],
    "condition": [{"condition": "state", "entity_id": "binary_sensor.zhimi_cn_873345887_pa6_seating_state_p_2_5", "state": "off"}],
    "action": [{"service": "switch.turn_off", "target": {"entity_id": "switch.xiaomi_cn_921633051_na2_ventilation_p_4_8"}}],
    "mode": "restart"
}

# --- Group 4: Safety & Alerts ---
automations["water_leak_alert"] = {
    "alias": "安全守护：水浸报警",

    "trigger": [
        {"platform": "state", "entity_id": "binary_sensor.xiaomi_cn_blt_3_1n2u88p650c02_oh83w_submersion_state_p_2_1006", "from": "off", "to": "on"},
        {"platform": "state", "entity_id": "binary_sensor.xiaomi_cn_blt_3_1n2u88p650c02_oh83w_submersion_state_top_p_2_1123", "from": "off", "to": "on"}
    ],
    "action": [
        {"service": "light.turn_on", "target": {"entity_id": "light.moes_matter_light"}, "data": {"flash": "long", "rgb_color": [255, 0, 0]}},
        {"service": "notify.mobile_app_iphone18_2", "data": {"title": "【紧急】发现漏水！", "message": "厨房水浸传感器检测到漏水，请尽快处理。", "data": {"push": {"sound": "US-EN-Morgan-Freeman-Kitchen-Is-Flooding.wav", "critical": 1}}}}
    ],
    "mode": "single"
}

# --- Group 4b: Apple TV + Trytogo Light ---
automations["appletv_trytogo_on"] = {
    "alias": "影音联动：Apple TV 开启时打开 Trytogo 灯",
    "trigger": [{"platform": "state", "entity_id": "media_player.dian_shi_ji", "from": "off", "to": ["idle", "playing", "paused"]}],
    "action": [{"service": "light.turn_on", "target": {"entity_id": "light.trytogo"}}],
    "mode": "single",
}

automations["appletv_trytogo_off"] = {
    "alias": "影音联动：Apple TV 关闭时关闭 Trytogo 灯",
    "trigger": [{"platform": "state", "entity_id": "media_player.dian_shi_ji", "to": "off"}],
    "action": [{"service": "light.turn_off", "target": {"entity_id": "light.trytogo"}}],
    "mode": "single",
}

# --- Group 5: Presence Lighting (人来灯开，人走灯灭) ---
# 可选字段: lux — 有则加光照条件; off_delay — 有则在关灯 trigger 加延迟
PRESENCE_TOGGLE = "input_boolean.ren_lai_ren_zou_zi_dong_deng"

PRESENCE_ROOMS = [
    {
        "id": "master_bath",
        "name": "主卫",
        "sensor": "binary_sensor.linp_cn_1139276665_hb01_occupancy_status_p_2_1",
        "lux": "sensor.linp_cn_1139276665_hb01_illumination_p_2_5",
        "light": [  # 不含浴霸灯
            "light.linp_cn_950194815_ld6bcw_s_2_light",       # 存在筒射灯
            "light.090615_cn_2000228017_milg05_s_2_light",     # 射灯 1
            "light.090615_cn_2000257106_milg05_s_2_light",     # 射灯 2
        ],
    },
    {
        "id": "guest_bath",
        "name": "次卫",
        "sensor": "binary_sensor.linp_cn_1139296986_hb01_occupancy_status_p_2_1",
        "lux": "sensor.linp_cn_1139296986_hb01_illumination_p_2_5",
        "light": [  # 不含浴霸灯
            "light.linp_cn_949833026_ld6bcw_s_2_light",       # 存在筒射灯
            "light.090615_cn_2000254608_milg05_s_2_light",     # 射灯 1
            "light.090615_cn_2000276840_milg05_s_2_light",     # 射灯 2
        ],
    },
    {
        "id": "master_bedroom",
        "name": "主卧",
        "sensor": "binary_sensor.linp_cn_949882702_ld6bcw_occupancy_status_p_5_1",
        "off_delay": "00:01:00",
        "light": [
            "light.intelligent_drive_power_supply_22",         # 主灯
            "light.intelligent_drive_power_supply_20",         # 左射灯
            "light.intelligent_drive_power_supply_21",         # 右射灯
            "light.intelligent_drive_power_supply_18",         # 床头左射灯
            "light.intelligent_drive_power_supply_19",         # 床头右射灯
            "light.linp_cn_949882702_ld6bcw_s_2_light",       # 存在筒射灯
        ],
    },
    {
        "id": "guest_bedroom",
        "name": "次卧",
        "sensor": "binary_sensor.linp_cn_949847136_ld6bcw_occupancy_status_p_5_1",
        "off_delay": "00:01:00",
        "light": [
            "light.intelligent_drive_power_supply_5",          # 格栅灯
            "light.090615_cn_2000281237_milg05_s_2_light",     # 射灯 1
            "light.090615_cn_2000196741_milg05_s_2_light",     # 射灯 2
            "light.linp_cn_949847136_ld6bcw_s_2_light",       # 存在筒射灯
        ],
    },
    {
        "id": "kitchen",
        "name": "厨房",
        "sensor": "binary_sensor.linp_cn_blt_3_1n4pve0so4g02_es4b_occupancy_status_p_2_1078",
        "off_delay": "00:01:00",
        "light": [
            "light.intelligent_drive_power_supply_11",         # 平板灯
            "light.intelligent_drive_power_supply_12",         # 射灯
        ],
    },
]

for room in PRESENCE_ROOMS:
    # --- 人来灯开 ---
    on_conditions = [
        {"condition": "state", "entity_id": PRESENCE_TOGGLE, "state": "on"},
    ]
    if "lux" in room:
        on_conditions.append({"condition": "numeric_state", "entity_id": room["lux"], "below": 30})
    on_conditions.append({"condition": "state", "entity_id": room["light"], "state": "off"})

    automations[f"presence_light_on_{room['id']}"] = {
        "alias": f"人来灯开：{room['name']}",
        "trigger": [{"platform": "state", "entity_id": room["sensor"], "from": "off", "to": "on"}],
        "condition": on_conditions,
        "action": [{"service": "light.turn_on", "target": {"entity_id": room["light"]}}],
        "mode": "single",
    }
    # --- 人走灯灭 ---
    off_trigger = {"platform": "state", "entity_id": room["sensor"], "from": "on", "to": "off"}
    if "off_delay" in room:
        off_trigger["for"] = room["off_delay"]

    automations[f"presence_light_off_{room['id']}"] = {
        "alias": f"人走灯灭：{room['name']}",
        "trigger": [off_trigger],
        "condition": [
            {"condition": "state", "entity_id": PRESENCE_TOGGLE, "state": "on"},
        ],
        "action": [{"service": "light.turn_off", "target": {"entity_id": room["light"]}}],
        "mode": "single",
    }


# --- Group 6: Leave Home Guard ---
automations["leave_home_guard"] = {
    "alias": "离家守护：离家且无人则全关",
    "description": "在家确认关闭且非访客模式，自动关闭所有设备",
    "trigger": [{"platform": "state", "entity_id": "input_boolean.zai_jia_que_ren", "from": "on", "to": "off"}],
    "condition": [{"condition": "state", "entity_id": "input_boolean.fang_ke_mo_shi", "state": "off"}],
    "action": [
        {"service": "light.turn_off", "target": {"entity_id": [
            "light.ke_ting_deng_guang", "light.xi_chu_deng_guang", "light.chu_fang_deng_guang",
            "light.zhu_wo_deng_guang", "light.zhu_wei_deng_guang", "light.ci_wo_deng_guang",
            "light.ci_wei_deng_guang", "light.shu_fang_deng_guang", "light.yang_tai_deng_guang",
        ]}},
        {"service": "climate.turn_off", "target": {"entity_id": [
            "climate.lemesh_cn_2000792394_air02", "climate.lemesh_cn_2000792363_air02",
            "climate.lemesh_cn_2000792396_air02", "climate.lemesh_cn_2000792347_air02",
            "climate.lemesh_cn_2000794495_air02", "climate.tofan_cn_948856816_wk01",
        ]}},
        {"service": "media_player.turn_off", "target": {"entity_id": [
            "media_player.tcl_85q10l_pro", "media_player.ke_ting", "media_player.xi_chu",
        ]}},
        {"service": "notify.mobile_app_iphone18_2", "data": {
            "title": "离家守护已激活",
            "message": "在家确认已关闭，灯光、空调、影音设备已自动关闭。",
        }},
    ],
    "mode": "single",
}

# --- Group 7: Pet Feeder Daily Tracking ---
_feeder_feed_success = "event.mmgg_cn_467135245_inland_feedsuccess_e_4_1"
_feeder_daily_counter = "counter.pet_feeder_daily_portions"

# --- Group 7b: Pokémon → Material You Theme ---
_material_you_image_url = "input_text.material_you_image_url_2f34e1e49f2e405d974d3169792c64d0"

automations["pokemon_material_you_theme"] = {
    "alias": "主题联动：宝可梦图片同步 Material You",
    "trigger": [{"platform": "state", "entity_id": "input_text.pokemon_sprite"}],
    "condition": [
        {"condition": "template", "value_template": "{{ trigger.to_state.state not in ['unknown', 'unavailable', ''] }}"},
    ],
    "action": [
        {"service": "input_text.set_value", "target": {"entity_id": _material_you_image_url}, "data": {"value": "{{ trigger.to_state.state }}"}},
    ],
    "mode": "single",
}

automations["pet_feeder_daily_increment"] = {
    "alias": "宠物喂食：出粮计数累加",
    "trigger": [{"platform": "state", "entity_id": _feeder_feed_success}],
    "condition": [],
    "action": [
        {"repeat": {
            "count": "{{ trigger.to_state.attributes.get('\u5b9e\u9645\u51fa\u7cae\u4efd\u6570', 1) | int }}",
            "sequence": [{"service": "counter.increment", "target": {"entity_id": _feeder_daily_counter}}],
        }},
    ],
    "mode": "queued",
}

automations["pet_feeder_daily_reset"] = {
    "alias": "宠物喂食：每日计数重置",
    "trigger": [{"platform": "time", "at": "00:00:00"}],
    "condition": [],
    "action": [{"service": "counter.reset", "target": {"entity_id": _feeder_daily_counter}}],
    "mode": "single",
}


def ensure_counter(ws, msg_id, name, icon, initial=0, step=1, minimum=0, maximum=9999):
    """Create counter helper (idempotent — ignores 'already exists')."""
    ws.send(json.dumps({
        "id": msg_id,
        "type": "counter/create",
        "name": name,
        "icon": icon,
        "initial": initial,
        "step": step,
        "minimum": minimum,
        "maximum": maximum,
    }))
    result = json.loads(ws.recv())
    if result.get("success"):
        print(f"  [CREATED] counter: {name}")
    else:
        err = result.get("error", {}).get("message", "?")
        if "already" in err.lower():
            print(f"  [EXISTS] counter: {name}")
        else:
            print(f"  [FAIL] counter: {name}: {err}")
    return msg_id + 1


def ensure_input_boolean(ws, msg_id, name, icon, existing_names):
    """Create input_boolean helper only if not already present.

    HA creates duplicates with _2/_3 suffix instead of erroring, so check first.
    """
    if name in existing_names:
        print(f"  [EXISTS] {name}")
        return msg_id
    ws.send(json.dumps({
        "id": msg_id,
        "type": "input_boolean/create",
        "name": name,
        "icon": icon,
    }))
    result = json.loads(ws.recv())
    if result.get("success"):
        print(f"  [CREATED] {name}")
    else:
        print(f"  [FAIL] {name}: {result.get('error', {}).get('message', '?')}")
    return msg_id + 1


if __name__ == "__main__":
    print("Applying Grouped Automations...")
    for aid, config in automations.items():
        put_automation(aid, config)
    call_service("automation", "reload")

    # Ensure input_boolean helpers exist
    print("\nEnsuring helpers...")
    ws_url = HA_URL.replace("https://", "wss://") + "/api/websocket"
    ws = websocket.create_connection(ws_url, sslopt={"cert_reqs": ssl.CERT_NONE})
    msg = json.loads(ws.recv())
    ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
    msg = json.loads(ws.recv())
    assert msg["type"] == "auth_ok", f"Auth failed: {msg}"

    # Fetch existing input_boolean names to avoid creating duplicates
    existing_bool_names = {
        s["attributes"].get("friendly_name")
        for s in api("GET", "/api/states")
        if s["entity_id"].startswith("input_boolean.")
    }

    mid = 100
    mid = ensure_input_boolean(ws, mid, "人来人走自动灯", "mdi:motion-sensor", existing_bool_names)
    mid = ensure_input_boolean(ws, mid, "在家确认", "mdi:home-account", existing_bool_names)
    mid = ensure_input_boolean(ws, mid, "访客模式", "mdi:account-group", existing_bool_names)

    # Ensure counter helpers exist
    print("\nEnsuring counter helpers...")
    mid = ensure_counter(ws, mid, "pet_feeder_daily_portions", "mdi:counter")
    ws.close()

    # Turn on by default
    call_service("input_boolean", "turn_on", {"entity_id": PRESENCE_TOGGLE})
    print("Done.")
