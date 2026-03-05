#!/usr/bin/env python3
"""Create Adaptive Lighting instances for each area's spotlights/downlights."""

import json
import time

from ha_api import api


def create_instance(name, lights, options_override=None):
    """Create an adaptive_lighting config entry and configure its options."""
    # Step 1: Start config flow
    result = api("POST", "/api/config/config_entries/flow",
                 {"handler": "adaptive_lighting", "show_advanced_options": True})
    flow_id = result["flow_id"]

    # Step 2: Select "new"
    result = api("POST", f"/api/config/config_entries/flow/{flow_id}",
                 {"action": "new"})
    flow_id = result["flow_id"]

    # Step 3: Submit name
    result = api("POST", f"/api/config/config_entries/flow/{flow_id}",
                 {"name": name})
    entry_id = result["result"]["entry_id"]
    print(f"  Created entry: {entry_id}")

    # Step 4: Start options flow
    time.sleep(0.5)
    result = api("POST", "/api/config/config_entries/options/flow",
                 {"handler": entry_id, "show_advanced_options": True})
    options_flow_id = result["flow_id"]

    # Step 5: Submit options with lights
    options = {
        "lights": lights,
        "interval": 90,
        "transition": 45,
        "initial_transition": 1,
        "min_brightness": 1,
        "max_brightness": 100,
        "min_color_temp": 2000,
        "max_color_temp": 5500,
        "sleep_brightness": 1,
        "sleep_rgb_or_color_temp": "color_temp",
        "sleep_color_temp": 1000,
        "take_over_control": True,
        "detect_non_ha_changes": False,
        "intercept": True,
        "multi_light_intercept": True,
    }
    if options_override:
        options.update(options_override)

    result = api("POST",
                 f"/api/config/config_entries/options/flow/{options_flow_id}",
                 options)
    print(f"  Options set: {result.get('type')}")
    return entry_id


# ============================================================
# Area definitions: name → spotlight/downlight entities (no strips)
# ============================================================
AREAS = {
    "客厅": [
        "light.intelligent_drive_power_supply_16",           # 泛光灯
        "light.intelligent_power",                           # 长格栅灯
        "light.intelligent_drive_power_supply_15",           # 格栅灯 1
        "light.intelligent_drive_power_supply_17",           # 格栅灯 2
        "light.intelligent_drive_power_supply_14",           # 格栅灯 3
        "light.intelligent_drive_power_supply_13",           # 折叠格栅灯
        "light.wlg_cn_949473222_wy0a06_s_2_light",          # 背景墙射灯 1
        "light.wlg_cn_949429122_wy0a06_s_2_light",          # 背景墙射灯 2
        "light.gdds_cn_2080299638_wy0a02_s_2_light",        # 节律筒射灯
        "light.wlg_cn_949440999_wy0a06_s_2_light",          # 筒射灯 1
        "light.wlg_cn_949442390_wy0a06_s_2_light",          # 筒射灯 2
        "light.090615_cn_2000236373_milg05_s_2_light",       # 射灯 1
        "light.090615_cn_2000254702_milg05_s_2_light",       # 射灯 2
    ],
    "西厨": [
        "light.intelligent_drive_power_supply",              # 厨房入口射灯
        "light.intelligent_drive_power_supply_2",            # 背景墙
        "light.intelligent_drive_power_supply_3",            # 进门射灯
        "light.intelligent_drive_power_supply_4",            # Spotlight
        "light.wlg_cn_949413732_wy0a06_s_2_light",          # 筒射灯 1
        "light.wlg_cn_949433559_wy0a06_s_2_light",          # 筒射灯 2
        "light.wlg_cn_949433582_wy0a06_s_2_light",          # 筒射灯 3
        "light.wlg_cn_949435731_wy0a06_s_2_light",          # 筒射灯 4
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
    "阳台": [
        "light.wlg_cn_949198312_wy0a06_s_2_light",          # 筒射灯 1
        "light.wlg_cn_949459616_wy0a06_s_2_light",          # 筒射灯 2
    ],
}

# Skip areas that already have adaptive lighting configured
SKIP = {"厨房"}  # already exists as switch.adaptive_lighting_chu_fang

print("Setting up Adaptive Lighting for area spotlights...\n")

for area_name, lights in AREAS.items():
    if area_name in SKIP:
        print(f"[{area_name}] Skipped (already configured)")
        continue

    print(f"[{area_name}] {len(lights)} lights")
    try:
        create_instance(area_name, lights)
        print(f"  Done!\n")
    except Exception as e:
        print(f"  Error: {e}\n")

print("All done!")
