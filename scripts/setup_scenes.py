#!/usr/bin/env python3
"""Create scene modes for Home Assistant.

Note: HA server has ASCII locale, so scene config names must be English.
Chinese display names are set via entity_registry/update WebSocket.

Button bindings for scenes are managed by setup_wireless_switches.py.
"""

import json
import ssl
import time

import websocket

from ha_api import HA_URL, TOKEN, call_service, put_scene


# ============================================================
# Light entity lists by area
# ============================================================

# 客厅 - 主灯/射灯（不含灯带）
LIVING_ROOM_MAIN = [
    "light.intelligent_drive_power_supply_16",       # 泛光灯
    "light.intelligent_power",                       # 长格栅灯
    "light.intelligent_drive_power_supply_15",       # 格栅灯 1
    "light.intelligent_drive_power_supply_17",       # 格栅灯 2
    "light.intelligent_drive_power_supply_14",       # 格栅灯 3
    "light.intelligent_drive_power_supply_13",       # 折叠格栅灯
    "light.wlg_cn_949473222_wy0a06_s_2_light",      # 背景墙射灯 1
    "light.wlg_cn_949429122_wy0a06_s_2_light",      # 背景墙射灯 2
    "light.wlg_cn_949440999_wy0a06_s_2_light",      # 筒射灯 1
    "light.wlg_cn_949442390_wy0a06_s_2_light",      # 筒射灯 2
    "light.090615_cn_2000236373_milg05_s_2_light",   # 射灯 1
    "light.090615_cn_2000254702_milg05_s_2_light",   # 射灯 2
]
LIVING_ROOM_STRIP = "light.lemesh_cn_2023148762_wy0d02_s_2_light"  # 背景墙灯带

# 西厨 - 主灯/射灯
WEST_KITCHEN_MAIN = [
    "light.chu_fang_deng_guang",                     # 厨房灯光组（平板灯+射灯）
    "light.intelligent_drive_power_supply",          # 厨房入口射灯
    "light.intelligent_drive_power_supply_2",        # 背景墙
    "light.intelligent_drive_power_supply_3",        # 进门射灯
    "light.intelligent_drive_power_supply_4",        # Spotlight
    "light.wlg_cn_949413732_wy0a06_s_2_light",      # 筒射灯 1
    "light.wlg_cn_949433559_wy0a06_s_2_light",      # 筒射灯 2
    "light.wlg_cn_949433582_wy0a06_s_2_light",      # 筒射灯 3
    "light.wlg_cn_949435731_wy0a06_s_2_light",      # 筒射灯 4
]
WEST_KITCHEN_STRIPS = [
    "light.lemesh_cn_2000921741_wy0d02_s_2_light",  # 岛台灯带
    "light.lemesh_cn_2023151493_wy0d02_s_2_light",  # 鞋柜灯带
]

# 阳台
BALCONY_SPOTS = [
    "light.wlg_cn_949198312_wy0a06_s_2_light",      # 筒射灯 1
    "light.wlg_cn_949459616_wy0a06_s_2_light",      # 筒射灯 2
]
BALCONY_STRIP = "light.magical_homes_color_light"     # 灯带

# 主卧
MASTER_BEDROOM_ALL = [
    "light.intelligent_drive_power_supply_22",       # 主灯
    "light.intelligent_drive_power_supply_20",       # 左射灯
    "light.intelligent_drive_power_supply_21",       # 右射灯
    "light.intelligent_drive_power_supply_18",       # 床头左射灯
    "light.intelligent_drive_power_supply_19",       # 床头右射灯
    "light.lemesh_cn_2020771536_wy0d02_s_2_light",  # 床头灯带
    "light.lemesh_cn_2020803689_wy0d02_s_2_light",  # 入口灯带
    "light.linp_cn_949882702_ld6bcw_s_2_light",     # 存在筒射灯
    "light.yeelink_cn_125156913_lamp4_s_2_light",   # 台灯
]

# 主卫
MASTER_BATH_ALL = [
    "light.xiaomi_cn_921633051_na2_s_2_light",       # 浴霸灯
    "light.linp_cn_950194815_ld6bcw_s_2_light",     # 存在筒射灯
    "light.090615_cn_2000228017_milg05_s_2_light",   # 射灯 1
    "light.090615_cn_2000257106_milg05_s_2_light",   # 射灯 2
]

# Display name/icon by unique_id (scenes only)
DISPLAY_BY_UNIQUE_ID = {
    "hui_ke_mo_shi": {"name": "会客模式", "icon": "mdi:account-group", "desired_entity_id": "scene.hui_ke_mo_shi"},
    "ying_yin_mo_shi": {"name": "影音模式", "icon": "mdi:movie-open", "desired_entity_id": "scene.ying_yin_mo_shi"},
    "shui_mian_mo_shi": {"name": "睡眠模式", "icon": "mdi:weather-night", "desired_entity_id": "scene.shui_mian_mo_shi"},
}


# ============================================================
# Step 1: Create scenes (ASCII names only)
# ============================================================
print("=" * 60)
print("Step 1: Creating scenes")
print("=" * 60)

# --- 会客模式 (Guest Mode) ---
guest_entities = {}
for light in LIVING_ROOM_MAIN + WEST_KITCHEN_MAIN + BALCONY_SPOTS:
    guest_entities[light] = {"state": "on", "brightness": 230, "color_temp": 250}
for light in [LIVING_ROOM_STRIP, BALCONY_STRIP] + WEST_KITCHEN_STRIPS:
    guest_entities[light] = {"state": "on", "brightness": 204}

print("\n[Guest Mode]")
put_scene("hui_ke_mo_shi", {
    "name": "Guest Mode",
    "entities": guest_entities,
})

# --- 影音模式 (Cinema Mode) ---
cinema_entities = {}
for light in LIVING_ROOM_MAIN + WEST_KITCHEN_MAIN + BALCONY_SPOTS:
    cinema_entities[light] = {"state": "off"}
cinema_entities[LIVING_ROOM_STRIP] = {"state": "on", "brightness": 25, "color_temp": 500}
for strip in WEST_KITCHEN_STRIPS:
    cinema_entities[strip] = {"state": "off"}
cinema_entities["cover.linp_cn_2079472416_ec1db_s_2_curtain"] = {"state": "closed"}   # 客厅布帘
cinema_entities["cover.linp_cn_2079495198_ec1db_s_2_curtain"] = {"state": "closed"}   # 客厅纱帘

print("\n[Cinema Mode]")
put_scene("ying_yin_mo_shi", {
    "name": "Cinema Mode",
    "entities": cinema_entities,
})

# --- 睡眠模式 (Sleep Mode) ---
sleep_entities = {}
for light in MASTER_BEDROOM_ALL:
    sleep_entities[light] = {"state": "off"}
for light in MASTER_BATH_ALL:
    sleep_entities[light] = {"state": "off"}

print("\n[Sleep Mode]")
put_scene("shui_mian_mo_shi", {
    "name": "Sleep Mode",
    "entities": sleep_entities,
})

# ============================================================
# Step 2: Reload scenes
# ============================================================
print("\n" + "=" * 60)
print("Step 2: Reloading scenes")
print("=" * 60)

try:
    call_service("scene", "reload", {})
    print("Scenes reloaded!")
except Exception as e:
    print(f"Scene reload failed: {e}")

# ============================================================
# Step 3: Set Chinese display names and icons via entity registry
# ============================================================
print("\n" + "=" * 60)
print("Step 3: Setting Chinese display names & icons")
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

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 60)
print("Summary")
print("=" * 60)
print("Scenes created:")
print("  - scene.hui_ke_mo_shi    (会客模式)")
print("  - scene.ying_yin_mo_shi  (影音模式)")
print("  - scene.shui_mian_mo_shi (睡眠模式)")
print("\nButton bindings are managed by setup_wireless_switches.py")
