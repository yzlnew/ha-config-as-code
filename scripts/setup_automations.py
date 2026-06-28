#!/usr/bin/env python3
"""Centralized Automation Management: Organizes automations by logical groups."""

import json
import ssl
import time

import websocket

from ha_api import HA_URL, TOKEN, api, put_automation, delete_automation, call_service

# ============================================================
# Automation Definitions
# ============================================================
automations = {}
scripts = {}
IPHONE_NOTIFY_ENTITY = "notify.ye_zhi_ling_de_iphone"


def iphone_notify_action(title, message):
    return {
        "service": "notify.send_message",
        "target": {"entity_id": IPHONE_NOTIFY_ENTITY},
        "data": {"title": title, "message": message},
    }


DEPRECATED_AUTOMATION_IDS = [
    "chu_jia_quan_guan_bi_xin_feng",
    "chu_jia_quan_kai_qi_xin_feng",
    "home_keep_fresh_air_on",
]
MATTER_OFFLINE_SENSOR = "sensor.matter_light_offline_count"
MATTER_RECOVERY_PENDING = "input_boolean.matter_recovery_pending"
MATTER_RECOVERY_SCHEDULED_AT = "input_datetime.matter_recovery_scheduled_at"
WASHER_JOB_STATE = "sensor.xi_yi_ji_job_state"
AIRER_LIGHT = "light.xiaomi_cn_967167649_lyj3xs_s_3_light"
AUTOMATION_DISPLAY_BY_UNIQUE_ID = {
    "tv_sofa_track_on": {
        "name": "影音联动：电视机开启时打开沙发轨道灯",
        "icon": "mdi:track-light",
        "desired_entity_id": "automation.tv_sofa_track_on",
    },
    "home_turn_fresh_air_on": {
        "name": "环境自动：回家开启新风",
        "icon": "mdi:air-filter",
        "desired_entity_id": "automation.home_turn_fresh_air_on",
    },
    "ac_turn_fresh_air_off": {
        "name": "环境自动：开启空调关闭新风",
        "icon": "mdi:air-conditioner",
        "desired_entity_id": "automation.ac_turn_fresh_air_off",
    },
    "daily_pokemon": {
        "name": "每日宝可梦：每天更新图鉴",
        "icon": "mdi:pokeball",
        "desired_entity_id": "automation.daily_pokemon",
    },
    "pad5_charge_on": {
        "name": "自动充电：平板电量低于60开启",
        "icon": "mdi:battery-charging-60",
        "desired_entity_id": "automation.pad5_charge_on",
    },
    "pad5_charge_off": {
        "name": "自动充电：平板电量达到80关闭",
        "icon": "mdi:battery-80",
        "desired_entity_id": "automation.pad5_charge_off",
    },
    "battery_low_door_lock": {
        "name": "低电量：门锁电量不足通知",
        "icon": "mdi:battery-alert",
        "desired_entity_id": "automation.battery_low_door_lock",
    },
    "battery_low_fountain": {
        "name": "低电量：饮水机电量不足通知",
        "icon": "mdi:battery-alert",
        "desired_entity_id": "automation.battery_low_fountain",
    },
    "battery_low_temp_sensor": {
        "name": "低电量：温湿度计电量不足通知",
        "icon": "mdi:battery-alert",
        "desired_entity_id": "automation.battery_low_temp_sensor",
    },
    "battery_low_temp_sensor_2": {
        "name": "低电量：温湿度计2电量不足通知",
        "icon": "mdi:battery-alert",
        "desired_entity_id": "automation.battery_low_temp_sensor_2",
    },
    "battery_low_water_leak": {
        "name": "低电量：水浸卫士电量不足通知",
        "icon": "mdi:battery-alert",
        "desired_entity_id": "automation.battery_low_water_leak",
    },
    "laundry_washer_done": {
        "name": "清洁：洗衣机完成通知",
        "icon": "mdi:washing-machine",
        "desired_entity_id": "automation.laundry_washer_done",
    },
    "laundry_dryer_done": {
        "name": "清洁：烘干机完成通知",
        "icon": "mdi:tumble-dryer",
        "desired_entity_id": "automation.laundry_dryer_done",
    },
    "laundry_dishwasher_done": {
        "name": "清洁：洗碗机完成通知",
        "icon": "mdi:dishwasher",
        "desired_entity_id": "automation.laundry_dishwasher_done",
    },
    "curtain_master_bedroom_weekday_morning_half_open": {
        "name": "窗帘自动：工作日早上主卧开一半",
        "icon": "mdi:curtains",
        "desired_entity_id": "automation.curtain_master_bedroom_weekday_morning_half_open",
    },
    "curtain_living_room_sheer_close_after_arrive_home": {
        "name": "窗帘自动：晚上到家关闭客厅纱帘",
        "icon": "mdi:curtains-closed",
        "desired_entity_id": "automation.curtain_living_room_sheer_close_after_arrive_home",
    },
    "matter_recovery_schedule": {
        "name": "Matter 恢复：失联超过5盏预约",
        "icon": "mdi:calendar-clock",
        "desired_entity_id": "automation.matter_recovery_schedule",
    },
    "matter_recovery_run_scheduled": {
        "name": "Matter 恢复：早上4点执行",
        "icon": "mdi:restore-alert",
        "desired_entity_id": "automation.matter_recovery_run_scheduled",
    },
    "matter_recovery_cancel_schedule": {
        "name": "Matter 恢复：恢复后取消预约",
        "icon": "mdi:calendar-remove",
        "desired_entity_id": "automation.matter_recovery_cancel_schedule",
    },
    "laundry_washer_finished_airer_light_on": {
        "name": "洗衣联动：洗衣完成打开晾衣架灯",
        "icon": "mdi:hanger",
        "desired_entity_id": "automation.laundry_washer_finished_airer_light_on",
    },
    "s1e_button_2_toggle_ac": {
        "name": "S1E：无线键2切换空调",
        "icon": "mdi:air-conditioner",
        "desired_entity_id": "automation.s1e_button_2_toggle_ac",
    },
    "s1e_button_3_toggle_fresh_air": {
        "name": "S1E：无线键3切换新风",
        "icon": "mdi:air-filter",
        "desired_entity_id": "automation.s1e_button_3_toggle_fresh_air",
    },
    "s1e_button_4_toggle_desk_lamp": {
        "name": "S1E：无线键4切换桌面灯",
        "icon": "mdi:desk-lamp",
        "desired_entity_id": "automation.s1e_button_4_toggle_desk_lamp",
    },
    "s1e_button_5_toggle_study_light": {
        "name": "S1E：无线键5切换书房灯光",
        "icon": "mdi:ceiling-light",
        "desired_entity_id": "automation.s1e_button_5_toggle_study_light",
    },
    "s1e_button_6_scene_av": {
        "name": "S1E：无线键6影音模式",
        "icon": "mdi:movie-open",
        "desired_entity_id": "automation.s1e_button_6_scene_av",
    },
}
ENTITY_DISPLAY_BY_ENTITY_ID = {
    MATTER_OFFLINE_SENSOR: {
        "name": "Matter 灯失联数量",
        "icon": "mdi:lightbulb-alert",
    },
    MATTER_RECOVERY_PENDING: {
        "name": "Matter 恢复待执行",
        "icon": "mdi:calendar-clock",
    },
    MATTER_RECOVERY_SCHEDULED_AT: {
        "name": "Matter 恢复预约时间",
        "icon": "mdi:calendar-clock",
    },
    "script.matter_recovery_flow": {
        "name": "Matter 恢复：重启网络与服务",
        "icon": "mdi:restore-alert",
    },
    # S1E 无线键（场景键）重命名 + 图标。an_jian_1 的自动化（关其他灯）已先于本脚本创建。
    "sensor.s1e_54ef444fc2a8_an_jian_1": {"name": "书房无线键：关其他灯", "icon": "mdi:lightbulb-group-off"},
    "sensor.s1e_54ef444fc2a8_an_jian_2": {"name": "书房无线键：空调", "icon": "mdi:air-conditioner"},
    "sensor.s1e_54ef444fc2a8_an_jian_3": {"name": "书房无线键：新风", "icon": "mdi:air-filter"},
    "sensor.s1e_54ef444fc2a8_an_jian_4": {"name": "书房无线键：桌面灯", "icon": "mdi:desk-lamp"},
    "sensor.s1e_54ef444fc2a8_an_jian_5": {"name": "书房无线键：灯光", "icon": "mdi:ceiling-light"},
    "sensor.s1e_54ef444fc2a8_an_jian_6": {"name": "书房无线键：场景", "icon": "mdi:movie-open"},
}

scripts["matter_recovery_flow"] = {
    "alias": "Matter 恢复：重启网络与服务",
    "icon": "mdi:restore-alert",
    "sequence": [
        {"service": "persistent_notification.create", "data": {
            "title": "Matter 恢复开始",
            "message": "正在重启路由器网络服务，稍后会重启 Matter Server。",
            "notification_id": "matter_recovery_flow",
        }},
        {"service": "shell_command.matter_restart_router_network"},
        {"delay": "00:02:00"},
        {"service": "hassio.addon_restart", "data": {"addon": "core_matter_server"}},
        {"delay": "00:02:00"},
        iphone_notify_action("Matter 恢复已执行", "路由器网络服务和 Matter Server 已重启。当前失联数量：{{ states('sensor.matter_light_offline_count') }} / {{ state_attr('sensor.matter_light_offline_count', 'total') }}。"),
        {"service": "persistent_notification.create", "data": {
            "title": "Matter 恢复已执行",
            "message": "路由器网络服务和 Matter Server 已重启。请查看 dashboard 的 Matter 灯失联数量。",
            "notification_id": "matter_recovery_flow",
        }},
    ],
    "mode": "single",
}

# Note: Physical Switch Bindings (会客/影音/睡眠) are managed by setup_scenes.py
# which handles both ON and OFF directions. Do not duplicate here.

# --- Group 1: Environment & Climate ---
AC_ENTITIES = [
    "climate.lemesh_cn_2000792394_air02",  # 客厅空调
    "climate.lemesh_cn_2000792363_air02",  # 主卧空调
    "climate.lemesh_cn_2000792396_air02",  # 次卧空调
    "climate.lemesh_cn_2000792347_air02",  # 书房空调
    "climate.lemesh_cn_2000792371_air02",  # 西厨空调
    "climate.lemesh_cn_2000794495_air02",  # 背景空调
]
FRESH_AIR_ENTITY = "fan.tofan_cn_948856816_wk01_s_3_air_fresh"

automations["bath_dehumidification_on"] = {
    "alias": "环境自动：主卫除湿开启",

    "trigger": [
        {"platform": "numeric_state", "entity_id": "sensor.xiaomi_cn_921633051_na2_relative_humidity_p_11_9", "above": 80},
    ],
    "condition": [],
    "action": [{"service": "switch.turn_on", "target": {"entity_id": "switch.xiaomi_cn_921633051_na2_ventilation_p_4_8"}}],
    "mode": "single"
}

automations["bath_dehumidification_off"] = {
    "alias": "环境自动：主卫除湿关闭",

    "trigger": [
        {"platform": "numeric_state", "entity_id": "sensor.xiaomi_cn_921633051_na2_relative_humidity_p_11_9", "below": 65, "for": {"minutes": 2}},
        {"platform": "state", "entity_id": "binary_sensor.linp_cn_1139276665_hb01_occupancy_status_p_2_1", "to": "off", "for": {"minutes": 10}},
    ],
    "condition": [{"condition": "state", "entity_id": "switch.xiaomi_cn_921633051_na2_ventilation_p_4_8", "state": "on"}],
    "action": [{"service": "switch.turn_off", "target": {"entity_id": "switch.xiaomi_cn_921633051_na2_ventilation_p_4_8"}}],
    "mode": "single"
}

automations["home_turn_fresh_air_on"] = {
    "alias": "环境自动：回家开启新风",
    "description": "在家确认从关闭变为开启时打开新风；在家期间手动关闭后不再自动开启。",
    "trigger": [
        {"platform": "state", "entity_id": "input_boolean.zai_jia_que_ren", "from": "off", "to": "on"},
    ],
    "condition": [
        {"condition": "template", "value_template": "{{ states('fan.tofan_cn_948856816_wk01_s_3_air_fresh') != 'on' }}"},
    ],
    "action": [{"service": "fan.turn_on", "target": {"entity_id": "fan.tofan_cn_948856816_wk01_s_3_air_fresh"}}],
    "mode": "single",
}

automations["ac_turn_fresh_air_off"] = {
    "alias": "环境自动：开启空调关闭新风",
    "description": "任一空调从关闭切换为开启状态时，自动关闭新风机。",
    "trigger": [{"platform": "state", "entity_id": AC_ENTITIES, "from": "off"}],
    "condition": [{"condition": "state", "entity_id": FRESH_AIR_ENTITY, "state": "on"}],
    "action": [{"service": "fan.turn_off", "target": {"entity_id": FRESH_AIR_ENTITY}}],
    "mode": "single",
}

# --- Group 3: Leave & Welcome Home ---
# leave_home_guard is managed by create_leave_home_automation.py (input_boolean-based version)

automations["welcome_home_mode"] = {
    "alias": "安全守护：欢迎回家",

    "trigger": [
        {"platform": "state", "entity_id": "input_boolean.zai_jia_que_ren", "from": "off", "to": "on"},
        {"platform": "state", "entity_id": "event.lumi_cn_1011935590_bzacn1_lock_opened_e_2_1"},
    ],
    "condition": [
        {"condition": "template", "value_template": "{{ now().hour >= 17 or now().hour < 2 }}"},
        {"condition": "template", "value_template": "{{ [states('sensor.linp_cn_2079472416_ec1db_illumination_p_3_1') | float(999), states('sensor.linp_cn_2079495198_ec1db_illumination_p_3_1') | float(999)] | max < 30 }}"},
    ],
    "action": [
        {"service": "input_boolean.turn_on", "target": {"entity_id": "input_boolean.ren_lai_ren_zou_zi_dong_deng"}},
        {"service": "light.turn_on", "target": {"entity_id": [
            "light.intelligent_drive_power_supply",          # 厨房入口射灯
            "light.intelligent_drive_power_supply_3",        # 进门射灯
        ]}},
    ],
    "mode": "single"
}

# --- Group 3a: Curtains ---
automations["curtain_master_bedroom_weekday_morning_half_open"] = {
    "alias": "窗帘自动：工作日早上主卧开一半",
    "description": "周一到周五 8:30 将主卧窗帘开到 50%。",
    "trigger": [{"platform": "time", "at": "08:30:00"}],
    "condition": [
        {"condition": "time", "weekday": ["mon", "tue", "wed", "thu", "fri"]},
    ],
    "action": [{
        "service": "cover.set_cover_position",
        "target": {"entity_id": "cover.bean_cn_1158897918_ct06_s_2_curtain"},
        "data": {"position": 50},
    }],
    "mode": "single",
}

automations["curtain_living_room_sheer_close_after_arrive_home"] = {
    "alias": "窗帘自动：晚上到家关闭客厅纱帘",
    "description": "在家确认从离家变为在家，且时间为 17:00 到次日 02:00 时，关闭客厅纱帘。",
    "trigger": [
        {"platform": "state", "entity_id": "input_boolean.zai_jia_que_ren", "from": "off", "to": "on"},
    ],
    "condition": [
        {"condition": "template", "value_template": "{{ now().hour >= 17 or now().hour < 2 }}"},
        {"condition": "template", "value_template": "{{ states('cover.linp_cn_2079495198_ec1db_s_2_curtain') not in ['closed', 'unavailable', 'unknown'] }}"},
    ],
    "action": [{
        "service": "cover.close_cover",
        "target": {"entity_id": "cover.linp_cn_2079495198_ec1db_s_2_curtain"},
    }],
    "mode": "single",
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
    "condition": [
        {"condition": "state", "entity_id": "binary_sensor.zhimi_cn_873345887_pa6_seating_state_p_2_5", "state": "off"},
        {"condition": "numeric_state", "entity_id": "sensor.xiaomi_cn_921633051_na2_relative_humidity_p_11_9", "below": 75},
    ],
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
        iphone_notify_action("【紧急】发现漏水！", "厨房水浸传感器检测到漏水，请尽快处理。"),
    ],
    "mode": "single"
}

# --- Group 4a: Matter Recovery ---
automations["matter_recovery_schedule"] = {
    "alias": "Matter 恢复：失联超过5盏预约",
    "description": "Matter 灯失联超过 5 盏时，预约到第二天早上 4 点执行恢复流程。",
    "trigger": [
        {"platform": "numeric_state", "entity_id": MATTER_OFFLINE_SENSOR, "above": 5, "for": {"minutes": 10}},
        {"platform": "homeassistant", "event": "start"},
        {"platform": "time_pattern", "minutes": "/30"},
    ],
    "condition": [
        {"condition": "numeric_state", "entity_id": MATTER_OFFLINE_SENSOR, "above": 5},
        {"condition": "state", "entity_id": MATTER_RECOVERY_PENDING, "state": "off"},
    ],
    "action": [
        {"service": "input_datetime.set_datetime", "target": {"entity_id": MATTER_RECOVERY_SCHEDULED_AT}, "data": {
            "datetime": "{{ (today_at('04:00') + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S') }}",
        }},
        {"service": "input_boolean.turn_on", "target": {"entity_id": MATTER_RECOVERY_PENDING}},
        iphone_notify_action("Matter 恢复已预约", "当前 {{ states('sensor.matter_light_offline_count') }} / {{ state_attr('sensor.matter_light_offline_count', 'total') }} 盏 Matter 灯失联，已预约 {{ states('input_datetime.matter_recovery_scheduled_at') }} 执行恢复流程。"),
    ],
    "mode": "single",
}

automations["matter_recovery_run_scheduled"] = {
    "alias": "Matter 恢复：早上4点执行",
    "description": "在预约日期 04:00 且 Matter 灯仍有 5 盏以上失联时，执行恢复流程。",
    "trigger": [{"platform": "time", "at": "04:00:00"}],
    "condition": [
        {"condition": "state", "entity_id": MATTER_RECOVERY_PENDING, "state": "on"},
        {"condition": "numeric_state", "entity_id": MATTER_OFFLINE_SENSOR, "above": 5},
        {"condition": "template", "value_template": "{{ states('input_datetime.matter_recovery_scheduled_at')[:10] == now().strftime('%Y-%m-%d') }}"},
    ],
    "action": [
        iphone_notify_action("Matter 恢复开始", "预约时间已到，开始执行路由器网络服务重启和 Matter Server 重启。"),
        {"service": "input_boolean.turn_off", "target": {"entity_id": MATTER_RECOVERY_PENDING}},
        {"service": "script.turn_on", "target": {"entity_id": "script.matter_recovery_flow"}},
    ],
    "mode": "single",
}

automations["matter_recovery_cancel_schedule"] = {
    "alias": "Matter 恢复：恢复后取消预约",
    "description": "如果预约执行前 Matter 灯失联数量降到 5 盏以内，自动取消待执行标记。",
    "trigger": [{"platform": "numeric_state", "entity_id": MATTER_OFFLINE_SENSOR, "below": 6, "for": {"minutes": 10}}],
    "condition": [{"condition": "state", "entity_id": MATTER_RECOVERY_PENDING, "state": "on"}],
    "action": [
        {"service": "input_boolean.turn_off", "target": {"entity_id": MATTER_RECOVERY_PENDING}},
        iphone_notify_action("Matter 恢复预约已取消", "Matter 灯失联数量已降到 {{ states('sensor.matter_light_offline_count') }} / {{ state_attr('sensor.matter_light_offline_count', 'total') }}，不再执行 04:00 恢复流程。"),
    ],
    "mode": "single",
}

# --- Group 4b: Apple TV + Trytogo Light ---
automations["appletv_trytogo_on"] = {
    "alias": "影音联动：Apple TV 开启时打开 Trytogo 灯",
    "trigger": [{"platform": "state", "entity_id": "media_player.dian_shi_ji", "from": ["off", "idle", "standby"], "to": ["idle", "playing", "paused"]}],
    "action": [{"service": "light.turn_on", "target": {"entity_id": "light.trytogo"}}],
    "mode": "single",
}

automations["appletv_trytogo_off"] = {
    "alias": "影音联动：Apple TV 关闭时关闭 Trytogo 灯",
    "trigger": [{"platform": "state", "entity_id": "media_player.dian_shi_ji", "to": "off"}],
    "action": [{"service": "light.turn_off", "target": {"entity_id": "light.trytogo"}}],
    "mode": "single",
}

automations["tv_sofa_track_on"] = {
    "alias": "影音联动：电视机开启时打开沙发轨道灯",
    "trigger": [{"platform": "state", "entity_id": "media_player.dian_shi_ji", "from": ["off", "idle", "standby"], "to": ["idle", "playing", "paused"]}],
    "action": [{"service": "light.turn_on", "target": {"entity_id": "light.ke_ting_sha_fa_gui_dao"}}],
    "mode": "single",
}

# --- Group 4c: Adaptive Lighting bridge for ESPHome BLE lamps ---
automations["adaptive_lighting_laifen_bridge"] = {
    "alias": "自适应照明：Laifen 跟随书房",
    "trigger": [
        {"platform": "state", "entity_id": [
            "switch.esp32_d1_mini_laifen_bridge_laifen_master_light",
            "switch.esp32_d1_mini_laifen_bridge_laifen_upper_light",
            "switch.esp32_d1_mini_laifen_bridge_laifen_lower_light",
        ], "from": "off", "to": "on"},
    ],
    "condition": [
        {"condition": "state", "entity_id": "switch.adaptive_lighting_shu_fang", "state": "on"},
        {"condition": "template", "value_template": "{{ is_state('switch.esp32_d1_mini_laifen_bridge_laifen_master_light', 'on') or is_state('switch.esp32_d1_mini_laifen_bridge_laifen_upper_light', 'on') or is_state('switch.esp32_d1_mini_laifen_bridge_laifen_lower_light', 'on') }}"},
    ],
    "action": [
        {"service": "number.set_value", "target": {"entity_id": "number.esp32_d1_mini_laifen_bridge_laifen_color_temperature"}, "data": {
            "value": "{% set base = state_attr('switch.adaptive_lighting_shu_fang', 'color_temp_kelvin') | float(5000) %}{% set clamped = [2700, [base, 6500] | min] | max %}{{ ((clamped / 100) | round(0) * 100) | int }}"
        }},
        {"service": "number.set_value", "target": {"entity_id": "number.esp32_d1_mini_laifen_bridge_laifen_upper_brightness"}, "data": {
            "value": "{% set base = state_attr('switch.adaptive_lighting_shu_fang', 'brightness_pct') | float(70) %}{% set clamped = [1, [base * 1.15, 100] | min] | max %}{{ clamped | round(0) | int }}"
        }},
        {"service": "number.set_value", "target": {"entity_id": "number.esp32_d1_mini_laifen_bridge_laifen_lower_brightness"}, "data": {
            "value": "{% set base = state_attr('switch.adaptive_lighting_shu_fang', 'brightness_pct') | float(70) %}{% set clamped = [1, [base * 0.30, 40] | min] | max %}{{ clamped | round(0) | int }}"
        }},
    ],
    "mode": "restart",
}

# --- Group 4d: Moonside state memory ---
MOONSIDE_LIGHT = "light.esp32_d1_mini_moonside_moonside_lamp"
MOONSIDE_BRIGHTNESS = "number.esp32_d1_mini_moonside_moonside_brightness"
MOONSIDE_ACCENT_RED = "number.esp32_d1_mini_moonside_moonside_accent_red"
MOONSIDE_ACCENT_GREEN = "number.esp32_d1_mini_moonside_moonside_accent_green"
MOONSIDE_ACCENT_BLUE = "number.esp32_d1_mini_moonside_moonside_accent_blue"
MOONSIDE_EFFECT = "select.esp32_d1_mini_moonside_moonside_dynamic_effect"

MOONSIDE_LAST_RED = "input_number.moonside_last_red"
MOONSIDE_LAST_GREEN = "input_number.moonside_last_green"
MOONSIDE_LAST_BLUE = "input_number.moonside_last_blue"
MOONSIDE_LAST_BRIGHTNESS = "input_number.moonside_last_brightness"
MOONSIDE_LAST_ACCENT_RED = "input_number.moonside_last_accent_red"
MOONSIDE_LAST_ACCENT_GREEN = "input_number.moonside_last_accent_green"
MOONSIDE_LAST_ACCENT_BLUE = "input_number.moonside_last_accent_blue"
MOONSIDE_LAST_EFFECT = "input_text.moonside_last_effect"

automations["moonside_state_save"] = {
    "alias": "灯光记忆：Moonside 关闭时记录状态",
    "trigger": [{"platform": "state", "entity_id": MOONSIDE_LIGHT, "from": "on", "to": "off"}],
    "condition": [{"condition": "template", "value_template": "{{ trigger.from_state is not none }}"}],
    "action": [
        {"service": "input_number.set_value", "target": {"entity_id": MOONSIDE_LAST_RED}, "data": {
            "value": "{% set rgb = trigger.from_state.attributes.rgb_color | default([], true) %}{{ rgb[0] if rgb | count > 2 else states('" + MOONSIDE_LAST_RED + "') | int(255) }}"
        }},
        {"service": "input_number.set_value", "target": {"entity_id": MOONSIDE_LAST_GREEN}, "data": {
            "value": "{% set rgb = trigger.from_state.attributes.rgb_color | default([], true) %}{{ rgb[1] if rgb | count > 2 else states('" + MOONSIDE_LAST_GREEN + "') | int(180) }}"
        }},
        {"service": "input_number.set_value", "target": {"entity_id": MOONSIDE_LAST_BLUE}, "data": {
            "value": "{% set rgb = trigger.from_state.attributes.rgb_color | default([], true) %}{{ rgb[2] if rgb | count > 2 else states('" + MOONSIDE_LAST_BLUE + "') | int(50) }}"
        }},
        {"service": "input_number.set_value", "target": {"entity_id": MOONSIDE_LAST_BRIGHTNESS}, "data": {
            "value": "{{ states('" + MOONSIDE_BRIGHTNESS + "') | int(states('" + MOONSIDE_LAST_BRIGHTNESS + "') | int(80)) }}"
        }},
        {"service": "input_number.set_value", "target": {"entity_id": MOONSIDE_LAST_ACCENT_RED}, "data": {
            "value": "{{ states('" + MOONSIDE_ACCENT_RED + "') | int(states('" + MOONSIDE_LAST_ACCENT_RED + "') | int(0)) }}"
        }},
        {"service": "input_number.set_value", "target": {"entity_id": MOONSIDE_LAST_ACCENT_GREEN}, "data": {
            "value": "{{ states('" + MOONSIDE_ACCENT_GREEN + "') | int(states('" + MOONSIDE_LAST_ACCENT_GREEN + "') | int(0)) }}"
        }},
        {"service": "input_number.set_value", "target": {"entity_id": MOONSIDE_LAST_ACCENT_BLUE}, "data": {
            "value": "{{ states('" + MOONSIDE_ACCENT_BLUE + "') | int(states('" + MOONSIDE_LAST_ACCENT_BLUE + "') | int(140)) }}"
        }},
        {"service": "input_text.set_value", "target": {"entity_id": MOONSIDE_LAST_EFFECT}, "data": {
            "value": "{{ states('" + MOONSIDE_EFFECT + "') if states('" + MOONSIDE_EFFECT + "') not in ['unknown', 'unavailable', 'none', ''] else 'Solid Color' }}"
        }},
    ],
    "mode": "queued",
}

automations["moonside_state_restore"] = {
    "alias": "灯光记忆：Moonside 开启时恢复状态",
    "trigger": [{"platform": "state", "entity_id": MOONSIDE_LIGHT, "from": "off", "to": "on"}],
    "action": [
        {"delay": {"milliseconds": 250}},
        {"service": "number.set_value", "target": {"entity_id": MOONSIDE_BRIGHTNESS}, "data": {
            "value": "{{ states('" + MOONSIDE_LAST_BRIGHTNESS + "') | int(80) }}"
        }},
        {"service": "number.set_value", "target": {"entity_id": MOONSIDE_ACCENT_RED}, "data": {
            "value": "{{ states('" + MOONSIDE_LAST_ACCENT_RED + "') | int(0) }}"
        }},
        {"service": "number.set_value", "target": {"entity_id": MOONSIDE_ACCENT_GREEN}, "data": {
            "value": "{{ states('" + MOONSIDE_LAST_ACCENT_GREEN + "') | int(0) }}"
        }},
        {"service": "number.set_value", "target": {"entity_id": MOONSIDE_ACCENT_BLUE}, "data": {
            "value": "{{ states('" + MOONSIDE_LAST_ACCENT_BLUE + "') | int(140) }}"
        }},
        {"service": "light.turn_on", "target": {"entity_id": MOONSIDE_LIGHT}, "data": {
            "rgb_color": [
                "{{ states('" + MOONSIDE_LAST_RED + "') | int(255) }}",
                "{{ states('" + MOONSIDE_LAST_GREEN + "') | int(180) }}",
                "{{ states('" + MOONSIDE_LAST_BLUE + "') | int(50) }}",
            ],
        }},
        {"choose": [{
            "conditions": [{
                "condition": "template",
                "value_template": "{{ states('" + MOONSIDE_LAST_EFFECT + "') not in ['Solid Color', 'unknown', 'unavailable', 'none', ''] }}",
            }],
            "sequence": [
                {"delay": {"milliseconds": 500}},
                {"service": "select.select_option", "target": {"entity_id": MOONSIDE_EFFECT}, "data": {
                    "option": "{{ states('" + MOONSIDE_LAST_EFFECT + "') }}"
                }},
            ],
        }]},
    ],
    "mode": "restart",
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
            "light.yeelink_cn_125156913_lamp4_s_2_light",     # 台灯
        ],
    },
    {
        "id": "study",
        "name": "书房",
        "sensor": "binary_sensor.izq_cn_1089128418_24_occupancy_status_p_2_1",
        "lux": "sensor.izq_cn_1089128418_24_illumination_p_2_5",
        "off_delay": "00:01:00",
        "turn_on_service": "homeassistant.turn_on",
        "turn_off_service": "homeassistant.turn_off",
        "light": [
            "switch.esp32_d1_mini_laifen_bridge_laifen_master_light",  # Laifen
            "light.esp32_d1_mini_moonside_moonside_lamp",              # Moonside
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
        {"condition": "state", "entity_id": "input_boolean.zai_jia_que_ren", "state": "on"},
    ]
    if "lux" in room:
        on_conditions.append({"condition": "numeric_state", "entity_id": room["lux"], "below": 30})
    on_conditions.append({"condition": "state", "entity_id": room["light"], "state": "off"})

    automations[f"presence_light_on_{room['id']}"] = {
        "alias": f"人来灯开：{room['name']}",
        "trigger": [{"platform": "state", "entity_id": room["sensor"], "from": "off", "to": "on"}],
        "condition": on_conditions,
        "action": [{"service": room.get("turn_on_service", "light.turn_on"), "target": {"entity_id": room["light"]}}],
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
        "action": [{"service": room.get("turn_off_service", "light.turn_off"), "target": {"entity_id": room["light"]}}],
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
        {"service": "fan.turn_off", "target": {"entity_id": "fan.tofan_cn_948856816_wk01_s_3_air_fresh"}},
        {"service": "input_boolean.turn_off", "target": {"entity_id": PRESENCE_TOGGLE}},
        iphone_notify_action("离家守护已激活", "在家确认已关闭，灯光、空调、影音设备和新风机已自动关闭。"),
    ],
    "mode": "single",
}

# --- Group 6b: Laundry ---
automations["laundry_washer_finished_airer_light_on"] = {
    "alias": "洗衣联动：洗衣完成打开晾衣架灯",
    "description": "洗衣机作业状态进入完成后，自动打开晾衣架灯。",
    "trigger": [{
        "platform": "state",
        "entity_id": WASHER_JOB_STATE,
        "to": "finish",
        "for": {"seconds": 10},
    }],
    "condition": [
        {"condition": "state", "entity_id": AIRER_LIGHT, "state": "off"},
    ],
    "action": [
        {"service": "light.turn_on", "target": {"entity_id": AIRER_LIGHT}},
    ],
    "mode": "single",
}

# --- Group 7: Pet Feeder Daily Tracking ---
_pet_todo_list = "todo.shopping_list"
_pet_drink_times = "sensor.yin_shui_ji_max_zhen_wu_xian_drink_times"
_pet_drinking = "binary_sensor.yin_shui_ji_max_zhen_wu_xian_pet_drinking"
_pet_litter_occupied = "binary_sensor.zhi_neng_mao_ce_suo_max_toilet_occupied"
_pet_sand_lack = "binary_sensor.zhi_neng_mao_ce_suo_max_sand_lack"
_pet_wastebin_full = "binary_sensor.zhi_neng_mao_ce_suo_max_wastebin_filled"
_feeder_feed_success = "event.mmgg_cn_467135245_inland_feedsuccess_e_4_1"
_feeder_daily_counter = "counter.pet_feeder_daily_portions"

automations["petkit_cat_toilet_notify"] = {
    "alias": "PetKit：Nova 如厕通知",
    "trigger": [{"platform": "state", "entity_id": _pet_litter_occupied, "from": "off", "to": "on"}],
    "action": [
        iphone_notify_action(
            "🐱 Nova 上厕所了",
            "{{ now().strftime(\"%H:%M\") }} Nova 进入了猫厕所 🚽",
        )
    ],
    "mode": "single",
}

# 注：drink_times 计数器噪声很大（PetKit 云端定时上报，常常凭空 +1/+2），
# pet_drinking 二元传感器才反映真实饮水会话。用后者做触发可避免误通知。
automations["petkit_cat_drink_notify"] = {
    "alias": "PetKit：Nova 喝水通知",
    "trigger": [{
        "platform": "state",
        "entity_id": _pet_drinking,
        "from": "off",
        "to": "on",
        "for": {"seconds": 5},
    }],
    "action": [
        iphone_notify_action(
            "🐱 Nova 喝水了",
            "💧 {{ now().strftime(\"%H:%M\") }} Nova 在喝水，今日累计 {{ states(\"sensor.yin_shui_ji_max_zhen_wu_xian_drink_times\") }} 次",
        )
    ],
    "mode": "single",
}

automations["petkit_sand_lack_notify"] = {
    "alias": "PetKit：缺猫砂通知",
    "trigger": [{"platform": "state", "entity_id": _pet_sand_lack, "from": "off", "to": "on"}],
    "action": [
        iphone_notify_action("⚠️ 猫砂不足", "🧹 猫厕所猫砂不足，请及时添加"),
        {
            "service": "todo.add_item",
            "target": {"entity_id": _pet_todo_list},
            "data": {"item": "补充猫砂"},
        },
    ],
    "mode": "single",
}

automations["petkit_wastebin_full_notify"] = {
    "alias": "PetKit：垃圾箱已满通知",
    "trigger": [{"platform": "state", "entity_id": _pet_wastebin_full, "from": "off", "to": "on"}],
    "action": [
        iphone_notify_action("⚠️ 垃圾箱已满", "🗑️ 猫厕所垃圾箱已满，请及时清理"),
        {
            "service": "todo.add_item",
            "target": {"entity_id": _pet_todo_list},
            "data": {"item": "清理猫厕所垃圾箱"},
        },
    ],
    "mode": "single",
}

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

# --- Group 8: Maintenance Notifications ---
LOW_BATTERY_AUTOMATIONS = {
    "battery_low_door_lock": {
        "alias": "低电量：门锁电量不足通知",
        "entity_id": "sensor.lumi_cn_1011935590_bzacn1_battery_level_p_4_1",
        "below": 20,
        "title": "门锁电量低",
        "message": "门锁电量剩余 {{ states('sensor.lumi_cn_1011935590_bzacn1_battery_level_p_4_1') }}%，请及时更换电池",
        "todo": "更换门锁电池",
    },
    "battery_low_fountain": {
        "alias": "低电量：饮水机电量不足通知",
        "entity_id": "sensor.yin_shui_ji_max_zhen_wu_xian_battery",
        "below": 20,
        "title": "饮水机电量低",
        "message": "饮水机电量剩余 {{ states('sensor.yin_shui_ji_max_zhen_wu_xian_battery') }}%，请及时更换电池",
        "todo": "更换饮水机电池",
    },
    "battery_low_temp_sensor": {
        "alias": "低电量：温湿度计电量不足通知",
        "entity_id": "sensor.miaomiaoc_cn_blt_3_1o36njo6occ03_t2_battery_level_p_3_1",
        "below": 15,
        "title": "温湿度计电量低",
        "message": "温湿度计电量剩余 {{ states('sensor.miaomiaoc_cn_blt_3_1o36njo6occ03_t2_battery_level_p_3_1') }}%，请及时更换电池",
        "todo": "更换温湿度计电池",
    },
    "battery_low_temp_sensor_2": {
        "alias": "低电量：温湿度计2电量不足通知",
        "entity_id": "sensor.miaomiaoc_cn_blt_3_1anos1mj8lg00_t2_battery_level_p_3_1",
        "below": 15,
        "title": "温湿度计2电量低",
        "message": "温湿度计2电量剩余 {{ states('sensor.miaomiaoc_cn_blt_3_1anos1mj8lg00_t2_battery_level_p_3_1') }}%，请及时更换电池",
        "todo": "更换温湿度计2电池",
    },
    "battery_low_water_leak": {
        "alias": "低电量：水浸卫士电量不足通知",
        "entity_id": "sensor.xiaomi_cn_blt_3_1n2u88p650c02_oh83w_battery_level_p_3_1003",
        "below": 15,
        "title": "水浸卫士电量低",
        "message": "水浸卫士电量剩余 {{ states('sensor.xiaomi_cn_blt_3_1n2u88p650c02_oh83w_battery_level_p_3_1003') }}%，请及时更换电池",
        "todo": "更换水浸卫士电池",
    },
}

for aid, spec in LOW_BATTERY_AUTOMATIONS.items():
    automations[aid] = {
        "alias": spec["alias"],
        "trigger": [{"platform": "numeric_state", "entity_id": spec["entity_id"], "below": spec["below"]}],
        "condition": [{"condition": "template", "value_template": "{{ trigger.from_state.state not in ['unknown', 'unavailable'] }}"}],
        "action": [
            iphone_notify_action(spec["title"], spec["message"]),
            {"service": "todo.add_item", "target": {"entity_id": _pet_todo_list}, "data": {"item": spec["todo"]}},
        ],
        "mode": "single",
    }

automations["pad5_charge_on"] = {
    "alias": "自动充电：平板电量低于60开启",
    "description": "小米平板5电量低于60%时自动打开传翔磁吸墙充",
    "trigger": [{"platform": "numeric_state", "entity_id": "sensor.xiao_mi_ping_ban_5_battery_level", "below": 60}],
    "condition": [{"condition": "state", "entity_id": "switch.zjcx_cn_2044030564_qcsw02_on_p_2_1", "state": "off"}],
    "action": [{"service": "switch.turn_on", "target": {"entity_id": "switch.zjcx_cn_2044030564_qcsw02_on_p_2_1"}}],
    "mode": "single",
}

automations["pad5_charge_off"] = {
    "alias": "自动充电：平板电量达到80关闭",
    "description": "小米平板5电量达到80%时自动关闭传翔磁吸墙充",
    "trigger": [{"platform": "numeric_state", "entity_id": "sensor.xiao_mi_ping_ban_5_battery_level", "above": 80}],
    "condition": [{"condition": "state", "entity_id": "switch.zjcx_cn_2044030564_qcsw02_on_p_2_1", "state": "on"}],
    "action": [{"service": "switch.turn_off", "target": {"entity_id": "switch.zjcx_cn_2044030564_qcsw02_on_p_2_1"}}],
    "mode": "single",
}

automations["daily_pokemon"] = {
    "alias": "每日宝可梦：每天更新图鉴",
    "description": "每天6:00自动运行 update_pokemon 脚本更新首页宝可梦卡片",
    "trigger": [{"platform": "time", "at": "06:00:00"}],
    "condition": [],
    "action": [{"service": "shell_command.update_pokemon"}],
    "mode": "single",
}

LAUNDRY_DONE_AUTOMATIONS = {
    "laundry_washer_done": {
        "alias": "清洁：洗衣机完成通知",
        "entity_id": "sensor.xi_yi_ji_machine_state",
        "from": "run",
        "to": "stop",
        "title": "洗衣机洗好了",
        "message": "衣服洗好了，记得取出来晾晒哦",
    },
    "laundry_dryer_done": {
        "alias": "清洁：烘干机完成通知",
        "entity_id": "sensor.hong_gan_ji_machine_state",
        "from": "run",
        "to": "stop",
        "title": "烘干机烘好了",
        "message": "衣服烘好了，记得取出来哦",
    },
    "laundry_dishwasher_done": {
        "alias": "清洁：洗碗机完成通知",
        "entity_id": "sensor.xi_wan_ji_operation_state",
        "from": "run",
        "to": "finished",
        "title": "洗碗机洗好了",
        "message": "碗碟洗好了，记得取出来哦",
    },
}

for aid, spec in LAUNDRY_DONE_AUTOMATIONS.items():
    automations[aid] = {
        "alias": spec["alias"],
        "trigger": [{"platform": "state", "entity_id": spec["entity_id"], "from": spec["from"], "to": spec["to"]}],
        "action": [
            iphone_notify_action(spec["title"], spec["message"]),
            {"service": "tts.cloud_say", "data": {
                "entity_id": "media_player.ke_ting",
                "message": spec["message"],
                "language": "zh-CN",
            }},
        ],
        "mode": "single",
    }

# --- Group 8: Aqara Cube (魔方控制器) ---
_cube_topic = "zigbee2mqtt/0x00158d00070822d2"

automations["cube_shake_toggle_apple_tv"] = {
    "alias": "魔方：摇晃开关 Apple TV",
    "description": "摇晃魔方切换 Apple TV 开关状态",
    "trigger": [{"platform": "mqtt", "topic": _cube_topic, "value_template": "{{ value_json.action | default('') }}", "payload": "shake"}],
    "condition": [],
    "action": [{
        "if": [{"condition": "state", "entity_id": "media_player.dian_shi_ji", "state": "standby"}],
        "then": [{"service": "remote.turn_on", "target": {"entity_id": "remote.dian_shi_ji"}}],
        "else": [{"service": "remote.turn_off", "target": {"entity_id": "remote.dian_shi_ji"}}],
    }],
    "mode": "single",
}

automations["cube_tap_toggle_litter_maintenance"] = {
    "alias": "魔方：敲击切换猫砂盆维护模式",
    "description": "双击魔方进入或退出猫砂盆维护模式",
    "trigger": [{"platform": "mqtt", "topic": _cube_topic, "value_template": "{{ value_json.action | default('') }}", "payload": "tap"}],
    "condition": [],
    "action": [{
        "if": [{"condition": "state", "entity_id": "button.zhi_neng_mao_ce_suo_max_maintenance_exit", "state": "unavailable"}],
        "then": [{"service": "button.press", "target": {"entity_id": "button.zhi_neng_mao_ce_suo_max_maintenance_start"}}],
        "else": [{"service": "button.press", "target": {"entity_id": "button.zhi_neng_mao_ce_suo_max_maintenance_exit"}}],
    }],
    "mode": "single",
}

# --- Group: S1E 无线键（场景键）绑定 ---
# 无线键只上报 PRESS/RELEASE 两态，触发 to "PRESS" 保证按一下只切换一次。
# 注意：依赖 S1E2HA 桥接上报；桥接 down 时 an_jian_* 为 unknown，按键不会触发。
# 无线键1（关其他灯）的自动化 s1e_button_1_other_lights_off 已先于本脚本创建，未在此重复定义。
automations["s1e_button_2_toggle_ac"] = {
    "alias": "S1E：无线键2切换空调",
    "description": "S1E 无线键2(空调)按下切换书房空调",
    "trigger": [{"platform": "state", "entity_id": "sensor.s1e_54ef444fc2a8_an_jian_2", "to": "PRESS"}],
    "condition": [],
    "action": [{"service": "homeassistant.toggle", "target": {"entity_id": "climate.lemesh_cn_2000792347_air02"}}],
    "mode": "single",
}

automations["s1e_button_3_toggle_fresh_air"] = {
    "alias": "S1E：无线键3切换新风",
    "description": "S1E 无线键3(新风)按下切换新风",
    "trigger": [{"platform": "state", "entity_id": "sensor.s1e_54ef444fc2a8_an_jian_3", "to": "PRESS"}],
    "condition": [],
    "action": [{"service": "homeassistant.toggle", "target": {"entity_id": "fan.tofan_cn_948856816_wk01_s_3_air_fresh"}}],
    "mode": "single",
}

automations["s1e_button_4_toggle_desk_lamp"] = {
    "alias": "S1E：无线键4切换桌面灯",
    "description": "S1E 无线键4(桌面灯)按下切换 Laifen+Moonside",
    "trigger": [{"platform": "state", "entity_id": "sensor.s1e_54ef444fc2a8_an_jian_4", "to": "PRESS"}],
    "condition": [],
    "action": [{"service": "homeassistant.toggle", "target": {"entity_id": [
        "switch.esp32_d1_mini_laifen_bridge_laifen_master_light",
        "light.esp32_d1_mini_moonside_moonside_lamp",
    ]}}],
    "mode": "single",
}

automations["s1e_button_5_toggle_study_light"] = {
    "alias": "S1E：无线键5切换书房灯光",
    "description": "S1E 无线键5(灯光)按下切换书房灯光",
    "trigger": [{"platform": "state", "entity_id": "sensor.s1e_54ef444fc2a8_an_jian_5", "to": "PRESS"}],
    "condition": [],
    "action": [{"service": "homeassistant.toggle", "target": {"entity_id": "light.shu_fang_deng_guang"}}],
    "mode": "single",
}

automations["s1e_button_6_scene_av"] = {
    "alias": "S1E：无线键6影音模式",
    "description": "S1E 无线键6(场景)按下激活影音模式",
    "trigger": [{"platform": "state", "entity_id": "sensor.s1e_54ef444fc2a8_an_jian_6", "to": "PRESS"}],
    "condition": [],
    "action": [{"service": "scene.turn_on", "target": {"entity_id": "scene.ying_yin_mo_shi"}}],
    "mode": "single",
}


def ensure_counter(ws, msg_id, name, icon, existing_names=None, initial=0, step=1, minimum=0, maximum=9999):
    """Create counter helper (idempotent — ignores 'already exists')."""
    if existing_names is not None and name in existing_names:
        print(f"  [EXISTS] counter: {name}")
        return msg_id

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


def put_script(script_id, config):
    """Create or update an HA script through the config API."""
    try:
        api("POST", f"/api/config/script/config/{script_id}", config)
        print(f"  [OK] script.{script_id}")
        return True
    except Exception as e:
        print(f"  [FAIL] script.{script_id} -> {e}")
        return False


def get_entity_registry_entries(ws, msg_id):
    """Fetch entity registry entries through the HA WebSocket API."""
    ws.send(json.dumps({"id": msg_id, "type": "config/entity_registry/list"}))
    result = json.loads(ws.recv())
    msg_id += 1
    if not result.get("success"):
        print(f"  [FAIL] entity registry list: {result.get('error', {}).get('message', '?')}")
        return None, msg_id
    return result.get("result", []), msg_id


def ensure_input_boolean(ws, msg_id, name, icon, existing_names, existing_entity_ids=None):
    """Create input_boolean helper only if not already present.

    HA creates duplicates with _2/_3 suffix instead of erroring, so check first.
    """
    desired_entity_id = f"input_boolean.{name}"
    if existing_entity_ids is not None and desired_entity_id in existing_entity_ids:
        print(f"  [EXISTS] {desired_entity_id}")
        return msg_id
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


def ensure_input_number(ws, msg_id, name, icon, existing_names, minimum, maximum, step, initial):
    """Create input_number helper only if not already present."""
    if name in existing_names:
        print(f"  [EXISTS] {name}")
        return msg_id
    ws.send(json.dumps({
        "id": msg_id,
        "type": "input_number/create",
        "name": name,
        "icon": icon,
        "min": minimum,
        "max": maximum,
        "step": step,
        "mode": "box",
        "initial": initial,
    }))
    result = json.loads(ws.recv())
    if result.get("success"):
        print(f"  [CREATED] {name}")
    else:
        print(f"  [FAIL] {name}: {result.get('error', {}).get('message', '?')}")
    return msg_id + 1


def ensure_input_text(ws, msg_id, name, icon, existing_names, initial):
    """Create input_text helper only if not already present."""
    if name in existing_names:
        print(f"  [EXISTS] {name}")
        return msg_id
    ws.send(json.dumps({
        "id": msg_id,
        "type": "input_text/create",
        "name": name,
        "icon": icon,
        "min": 0,
        "max": 100,
        "mode": "text",
        "initial": initial,
    }))
    result = json.loads(ws.recv())
    if result.get("success"):
        print(f"  [CREATED] {name}")
    else:
        print(f"  [FAIL] {name}: {result.get('error', {}).get('message', '?')}")
    return msg_id + 1


def ensure_input_datetime(ws, msg_id, name, icon, existing_entity_ids, has_date=True, has_time=True):
    """Create input_datetime helper only if the expected entity is missing."""
    desired_entity_id = f"input_datetime.{name}"
    if desired_entity_id in existing_entity_ids:
        print(f"  [EXISTS] {desired_entity_id}")
        return msg_id
    ws.send(json.dumps({
        "id": msg_id,
        "type": "input_datetime/create",
        "name": name,
        "icon": icon,
        "has_date": has_date,
        "has_time": has_time,
    }))
    result = json.loads(ws.recv())
    if result.get("success"):
        print(f"  [CREATED] {desired_entity_id}")
    else:
        print(f"  [FAIL] {desired_entity_id}: {result.get('error', {}).get('message', '?')}")
    return msg_id + 1


def update_entity_registry_display(ws, msg_id, display_by_unique_id):
    """Set entity_id/display metadata for automations created by this script."""
    registry, msg_id = get_entity_registry_entries(ws, msg_id)
    if registry is None:
        return msg_id

    uid_to_eid = {
        entry["unique_id"]: entry["entity_id"]
        for entry in registry
        if entry.get("entity_id", "").startswith("automation.")
    }

    for unique_id, display in display_by_unique_id.items():
        actual_eid = uid_to_eid.get(unique_id)
        if not actual_eid:
            print(f"  [SKIP] automation unique_id={unique_id} not found in registry")
            continue

        desired_eid = display["desired_entity_id"]
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

    return msg_id


def update_entity_registry_by_entity_id(ws, msg_id, display_by_entity_id):
    """Set display metadata for helpers, scripts and sensors by entity_id."""
    registry, msg_id = get_entity_registry_entries(ws, msg_id)
    if registry is None:
        return msg_id

    entries_by_entity_id = {entry.get("entity_id"): entry for entry in registry}
    for entity_id, display in display_by_entity_id.items():
        if entity_id not in entries_by_entity_id:
            print(f"  [SKIP] entity {entity_id} not found in registry")
            continue
        ws.send(json.dumps({
            "id": msg_id,
            "type": "config/entity_registry/update",
            "entity_id": entity_id,
            "name": display["name"],
            "icon": display["icon"],
        }))
        result = json.loads(ws.recv())
        status = "OK" if result.get("success") else f"FAIL: {result.get('error', {}).get('message', '?')}"
        print(f"  [{status}] {entity_id} -> {display['name']}")
        msg_id += 1

    return msg_id


if __name__ == "__main__":
    print("Applying Grouped Automations...")
    for aid in DEPRECATED_AUTOMATION_IDS:
        delete_automation(aid)
    print("Applying Scripts...")
    for sid, config in scripts.items():
        put_script(sid, config)
    call_service("script", "reload")

    print("\nApplying Automations...")
    for aid, config in automations.items():
        put_automation(aid, config)
    call_service("automation", "reload")

    # Ensure input_boolean helpers exist
    print("\nEnsuring helpers...")
    ws_url = HA_URL.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"
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
    existing_number_names = {
        s["attributes"].get("friendly_name")
        for s in api("GET", "/api/states")
        if s["entity_id"].startswith("input_number.")
    }
    existing_text_names = {
        s["attributes"].get("friendly_name")
        for s in api("GET", "/api/states")
        if s["entity_id"].startswith("input_text.")
    }
    existing_entity_ids = {
        s["entity_id"]
        for s in api("GET", "/api/states")
    }

    mid = 100
    mid = ensure_input_boolean(ws, mid, "人来人走自动灯", "mdi:motion-sensor", existing_bool_names)
    mid = ensure_input_boolean(ws, mid, "在家确认", "mdi:home-account", existing_bool_names)
    mid = ensure_input_boolean(ws, mid, "访客模式", "mdi:account-group", existing_bool_names)
    mid = ensure_input_number(ws, mid, "Moonside Last Red", "mdi:palette", existing_number_names, 0, 255, 1, 255)
    mid = ensure_input_number(ws, mid, "Moonside Last Green", "mdi:palette", existing_number_names, 0, 255, 1, 180)
    mid = ensure_input_number(ws, mid, "Moonside Last Blue", "mdi:palette", existing_number_names, 0, 255, 1, 50)
    mid = ensure_input_number(ws, mid, "Moonside Last Brightness", "mdi:brightness-6", existing_number_names, 0, 120, 1, 80)
    mid = ensure_input_number(ws, mid, "Moonside Last Accent Red", "mdi:palette-outline", existing_number_names, 0, 255, 1, 0)
    mid = ensure_input_number(ws, mid, "Moonside Last Accent Green", "mdi:palette-outline", existing_number_names, 0, 255, 1, 0)
    mid = ensure_input_number(ws, mid, "Moonside Last Accent Blue", "mdi:palette-outline", existing_number_names, 0, 255, 1, 140)
    mid = ensure_input_text(ws, mid, "Moonside Last Effect", "mdi:animation-play-outline", existing_text_names, "Solid Color")
    mid = ensure_input_boolean(ws, mid, "matter_recovery_pending", "mdi:calendar-clock", existing_bool_names, existing_entity_ids)
    mid = ensure_input_datetime(ws, mid, "matter_recovery_scheduled_at", "mdi:calendar-clock", existing_entity_ids)

    # Ensure counter helpers exist
    print("\nEnsuring counter helpers...")
    registry, mid = get_entity_registry_entries(ws, mid)
    existing_counter_names = None
    if registry is not None:
        existing_counter_names = {
            entry.get("name") or entry.get("original_name") or entry.get("unique_id")
            for entry in registry
            if entry.get("entity_id", "").startswith("counter.")
        }
    mid = ensure_counter(ws, mid, "pet_feeder_daily_portions", "mdi:counter", existing_counter_names)

    print("\nSetting automation display metadata...")
    time.sleep(1)
    mid = update_entity_registry_display(ws, mid, AUTOMATION_DISPLAY_BY_UNIQUE_ID)
    print("\nSetting helper/script/sensor display metadata...")
    mid = update_entity_registry_by_entity_id(ws, mid, ENTITY_DISPLAY_BY_ENTITY_ID)
    ws.close()

    # Turn on by default
    call_service("input_boolean", "turn_on", {"entity_id": PRESENCE_TOGGLE})
    print("Done.")
