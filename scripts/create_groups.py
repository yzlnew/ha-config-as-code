#!/usr/bin/env python3
"""Create light groups by area and a light strip group, then update dashboard."""

import time
from ha_api import api


def create_light_group(name, entities):
    """Create a light group helper via config flow."""
    # Step 1: Start flow
    result = api("POST","/api/config/config_entries/flow", {
        "handler": "group",
        "show_advanced_options": True,
    })
    flow_id = result["flow_id"]

    # Step 2: Select "light"
    result = api("POST",f"/api/config/config_entries/flow/{flow_id}", {
        "next_step_id": "light",
    })

    # Step 3: Submit group details
    result = api("POST",f"/api/config/config_entries/flow/{flow_id}", {
        "name": name,
        "entities": entities,
        "hide_members": False,
        "all": False,
    })

    if result.get("type") == "create_entry":
        entity_id = result.get("result", {}).get("entity_id", "unknown")
        print(f"  [OK] {name} -> {entity_id}")
        return entity_id
    else:
        print(f"  [FAIL] {name}: {result}")
        return None


# ============================================================
# Define all light groups
# ============================================================
groups = {
    "客厅灯光": [
        "light.intelligent_drive_power_supply_16",  # 泛光灯
        "light.intelligent_power",                   # 长格栅灯
        "light.intelligent_drive_power_supply_15",   # 格栅灯1
        "light.intelligent_drive_power_supply_17",   # 格栅灯2
        "light.intelligent_drive_power_supply_14",   # 格栅灯3
        "light.intelligent_drive_power_supply_13",   # 折叠格栅灯
        "light.lemesh_cn_2023148762_wy0d02_s_2_light",  # 背景墙灯带
        "light.wlg_cn_949473222_wy0a06_s_2_light",      # 背景墙射灯1
        "light.wlg_cn_949429122_wy0a06_s_2_light",      # 背景墙射灯2
        "light.wlg_cn_949440999_wy0a06_s_2_light",      # 筒射灯1
        "light.wlg_cn_949442390_wy0a06_s_2_light",      # 筒射灯2
        "light.090615_cn_2000236373_milg05_s_2_light",   # 射灯1
        "light.090615_cn_2000254702_milg05_s_2_light",   # 射灯2
    ],
    "客厅电视轨道": [                                     # 黑色明装轨道（靠近电视）
        "light.intelligent_drive_power_supply_13",       # 折叠格栅灯
        "light.intelligent_drive_power_supply_14",       # 格栅灯
    ],
    "客厅沙发轨道": [                                     # 白色明装轨道（沙发顶部）
        "light.intelligent_power",                       # 长格栅灯
        "light.intelligent_drive_power_supply_15",       # 格栅灯
    ],
    "客厅桌子轨道": [                                     # 黑色嵌入轨道（桌子上方）
        "light.intelligent_drive_power_supply_16",       # 泛光灯
        "light.intelligent_drive_power_supply_17",       # 格栅灯
    ],
    "厨房灯光": [
        "light.intelligent_drive_power_supply_11",  # 平板灯
        "light.intelligent_drive_power_supply_12",  # 射灯
    ],
    "西厨灯光": [
        "light.intelligent_drive_power_supply",     # 厨房入口射灯
        "light.intelligent_drive_power_supply_2",   # 背景墙
        "light.intelligent_drive_power_supply_3",   # 进门射灯
        "light.intelligent_drive_power_supply_4",   # Spotlight
        "light.lemesh_cn_2000921741_wy0d02_s_2_light",  # 岛台灯带
        "light.lemesh_cn_2023151493_wy0d02_s_2_light",  # 鞋柜灯带
        "light.wlg_cn_949413732_wy0a06_s_2_light",      # 筒射灯1
        "light.wlg_cn_949433559_wy0a06_s_2_light",      # 筒射灯2
        "light.wlg_cn_949433582_wy0a06_s_2_light",      # 筒射灯3
        "light.wlg_cn_949435731_wy0a06_s_2_light",      # 筒射灯4
    ],
    "主卧灯光": [
        "light.intelligent_drive_power_supply_22",       # 主灯
        "light.intelligent_drive_power_supply_20",       # 左射灯
        "light.intelligent_drive_power_supply_21",       # 右射灯
        "light.intelligent_drive_power_supply_18",       # 床头左射灯
        "light.intelligent_drive_power_supply_19",       # 床头右射灯
        "light.lemesh_cn_2020771536_wy0d02_s_2_light",  # 床头灯带
        "light.lemesh_cn_2020803689_wy0d02_s_2_light",  # 入口灯带
        "light.linp_cn_949882702_ld6bcw_s_2_light",     # 存在筒射灯
    ],
    "主卫灯光": [
        "light.xiaomi_cn_921633051_na2_s_2_light",       # 浴霸灯
        "light.linp_cn_950194815_ld6bcw_s_2_light",      # 存在筒射灯
        "light.090615_cn_2000228017_milg05_s_2_light",   # 射灯1
        "light.090615_cn_2000257106_milg05_s_2_light",   # 射灯2
    ],
    "次卧灯光": [
        "light.intelligent_drive_power_supply_5",        # 格栅灯
        "light.090615_cn_2000281237_milg05_s_2_light",   # 射灯1
        "light.090615_cn_2000196741_milg05_s_2_light",   # 射灯2
        "light.linp_cn_949847136_ld6bcw_s_2_light",      # 存在筒射灯
        "light.lemesh_cn_2001035175_wy0d02_s_2_light",   # 入口灯带
        "light.moes_matter_light",                        # 红色装饰灯
    ],
    "次卫灯光": [
        "light.yeelink_cn_945433772_v11_s_2_light",      # 浴霸灯
        "light.linp_cn_949833026_ld6bcw_s_2_light",      # 存在筒射灯
        "light.090615_cn_2000254608_milg05_s_2_light",   # 射灯1
        "light.090615_cn_2000276840_milg05_s_2_light",   # 射灯2
    ],
    "书房灯光": [
        "light.intelligent_drive_power_supply_6",        # 主灯
        "light.intelligent_drive_power_supply_8",        # 射灯1
        "light.intelligent_drive_power_supply_7",        # 射灯2
        "light.intelligent_drive_power_supply_9",        # 射灯3
        "light.intelligent_drive_power_supply_10",       # 射灯4
        "light.magical_homes_color_light_2",             # 书房灯带
        "light.lemesh_cn_2000705436_wy0d02_s_2_light",  # 色温灯
    ],
    "阳台灯光": [
        "light.magical_homes_color_light",               # 灯带
        "light.wlg_cn_949198312_wy0a06_s_2_light",      # 筒射灯1
        "light.wlg_cn_949459616_wy0a06_s_2_light",      # 筒射灯2
        "light.xiaomi_cn_967167649_lyj3xs_s_3_light",   # 晾衣机灯
    ],
    "全屋主灯带": [
        "light.magical_homes_color_light",               # 阳台-主灯带
        "light.magical_homes_color_light_2",             # 书房-主灯带
        "light.magical_homes_color_light_3",             # 客厅-主灯带1
        "light.magical_homes_color_light_4",             # 客厅-主灯带2
        "light.magical_homes_color_light_5",             # 通用主灯带
        "light.magical_homes_color_light_6",             # 电视区主灯带
    ],
    "全屋氛围灯带": [
        "light.lemesh_cn_2023148762_wy0d02_s_2_light",  # 客厅-背景墙氛围灯
        "light.lemesh_cn_2000921741_wy0d02_s_2_light",  # 西厨-岛台氛围灯
        "light.lemesh_cn_2023151493_wy0d02_s_2_light",  # 西厨-鞋柜氛围灯
        "light.lemesh_cn_2001035175_wy0d02_s_2_light",  # 次卧-入口氛围灯
        "light.lemesh_cn_2020771536_wy0d02_s_2_light",  # 主卧-床头氛围灯
        "light.lemesh_cn_2020803689_wy0d02_s_2_light",  # 主卧-入口氛围灯
        "light.lemesh_cn_2000705436_wy0d02_s_2_light",  # 书房-氛围色温灯
        "light.moes_matter_light",                        # 红色装饰灯 (虽然带 matter 但属于氛围)
    ],
    "所有灯光": [
        "light.ke_ting_deng_guang",                         # 客厅灯光组
        "light.xi_chu_deng_guang",                          # 西厨灯光组
        "light.chu_fang_deng_guang",                        # 厨房灯光组
        "light.zhu_wo_deng_guang",                          # 主卧灯光组
        "light.zhu_wei_deng_guang",                         # 主卫灯光组
        "light.ci_wo_deng_guang",                           # 次卧灯光组
        "light.ci_wei_deng_guang",                          # 次卫灯光组
        "light.shu_fang_deng_guang",                        # 书房灯光组
        "light.yang_tai_deng_guang",                        # 阳台灯光组
        "light.quan_wu_zhu_deng_dai",                       # 全屋主灯带
        "light.quan_wu_fen_wei_deng_dai",                   # 全屋氛围灯带
    ],
}

print("Creating light groups...")
created = {}
for name, entities in groups.items():
    entity_id = create_light_group(name, entities)
    if entity_id:
        created[name] = entity_id
    time.sleep(0.3)  # small delay between requests

print(f"\nCreated {len(created)}/{len(groups)} groups")
for name, eid in created.items():
    print(f"  {name}: {eid}")
