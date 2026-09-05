#!/usr/bin/env python3
"""Configure HomeKit Bridge to expose non-Matter devices to Apple Home.

Matter devices are excluded since they connect to HomeKit directly.
Only meaningful user-facing entities are included (no indicator lights,
no internal config switches, no browser_mod entities).
"""

from ha_api import api
import json
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── HomeKit Bridge desired configuration ─────────────────────────────────

# Domains to include in full (none of these contain Matter entities)
INCLUDE_DOMAINS = [
    "climate",       # 空调、浴霸、温控器
    "cover",         # 窗帘、晾衣机
    "fan",           # 新风、空气净化器
    "vacuum",        # 扫地机
]

# Domains that are available in the entity picker, but are filtered by the
# explicit INCLUDE_ENTITIES allowlist below.
SPECIFIC_ENTITY_DOMAINS = [
    "light",
    "media_player",
    "input_boolean",
    "button",
    "scene",
]

# Specific entities to include (from domains NOT fully included above)
INCLUDE_ENTITIES = [
    # ── 场景模式 ──
    "scene.hui_ke_mo_shi",              # 会客模式
    "scene.ying_yin_mo_shi",            # 影音模式
    "scene.shui_mian_mo_shi",            # 睡眠模式
    # ── 灯光组（按房间） ──
    "light.ke_ting_deng_guang",          # 客厅灯光
    "light.zhu_wo_deng_guang",           # 主卧灯光
    "light.ci_wo_deng_guang",            # 次卧灯光
    "light.shu_fang_deng_guang",         # 书房灯光
    "light.xi_chu_deng_guang",           # 西厨灯光
    "light.chu_fang_deng_guang",         # 厨房灯光
    "light.yang_tai_deng_guang",         # 阳台灯光
    "light.zhu_wei_deng_guang",          # 主卫灯光
    "light.ci_wei_deng_guang",           # 次卫灯光
    # ── 全屋灯光组 ──
    "light.quan_wu_fen_wei_deng_dai",    # 全屋氛围灯带
    "light.quan_wu_zhu_deng_dai",        # 全屋主灯带
    "light.suo_you_deng_guang",          # 所有灯光
    # ── 客厅非 Matter 灯具 ──
    "light.wlg_cn_949440999_wy0a06_s_2_light",           # 筒射灯 1
    "light.wlg_cn_949442390_wy0a06_s_2_light",           # 筒射灯 2
    "light.yeelight_cubematrix_0xc04e30f74108",           # Cube Matrix
    "light.trytogo",                                      # Trytogo
    "light.090615_cn_2000236373_milg05_s_2_light",        # 射灯 1
    "light.090615_cn_2000254702_milg05_s_2_light",        # 射灯 2
    "light.wlg_cn_949473222_wy0a06_s_2_light",            # 背景墙射灯 1
    "light.wlg_cn_949429122_wy0a06_s_2_light",            # 背景墙射灯 2
    "light.lemesh_cn_2023148762_wy0d02_s_2_light",        # 背景墙灯带
    "light.gdds_cn_2080299638_wy0a02_s_2_light",          # 节律筒射灯
    # ── 次卧非 Matter 灯具 ──
    "light.linp_cn_949847136_ld6bcw_s_2_light",           # 存在筒射灯
    "light.lemesh_cn_2001035175_wy0d02_s_2_light",        # 入口灯带
    "light.090615_cn_2000196741_milg05_s_2_light",        # 射灯 1
    "light.090615_cn_2000281237_milg05_s_2_light",        # 射灯 2
    # ── 次卫非 Matter 灯具 ──
    "light.linp_cn_949833026_ld6bcw_s_2_light",           # 存在筒射灯
    "light.090615_cn_2000254608_milg05_s_2_light",        # 射灯 1
    "light.090615_cn_2000276840_milg05_s_2_light",        # 射灯 2
    # ── 主卫非 Matter 灯具 ──
    "light.linp_cn_950194815_ld6bcw_s_2_light",           # 存在筒射灯
    "light.090615_cn_2000257106_milg05_s_2_light",        # 射灯 1
    "light.090615_cn_2000228017_milg05_s_2_light",        # 射灯 2
    # ── 功能灯 ──
    "light.xiaomi_cn_921633051_na2_s_2_light",   # 浴霸P1灯
    "light.yeelink_cn_945433772_v11_s_2_light",  # 浴霸灯
    "light.xiaomi_cn_967167649_lyj3xs_s_3_light", # 晾衣机灯
    # ── 主卧灯带 ──
    "light.lemesh_cn_2020771536_wy0d02_s_2_light", # 床头灯带
    "light.lemesh_cn_2020803689_wy0d02_s_2_light", # 入口灯带
    # ── 媒体播放器 ──
    "media_player.dian_shi_ji",          # 电视机
    "media_player.ke_ting",              # 客厅（Sonos）
    "media_player.tcl_85q10l_pro",       # TCL 电视
    "media_player.xi_chu",               # 西厨（Sonos）
    "media_player.xiaomi_cn_979970247_oh2",  # 智能音箱
    "media_player.zhu_wo",               # 主卧（Sonos）
    # ── 猫砂盆按钮 ──
    "button.zhi_neng_mao_ce_suo_max_scoop",              # 猫砂盆 清理
    "button.zhi_neng_mao_ce_suo_max_dump_litter",        # 猫砂盆 倾空猫砂
    "button.zhi_neng_mao_ce_suo_max_level_litter",        # 猫砂盆 抚平
    "button.zhi_neng_mao_ce_suo_max_maintenance_start",   # 猫砂盆 维护模式：开始
    "button.zhi_neng_mao_ce_suo_max_maintenance_exit",    # 猫砂盆 维护模式：退出
    # ── 虚拟开关 ──
    "input_boolean.zai_jia_que_ren",     # 在家确认（Apple Home 位置自动化）
    "input_boolean.fang_ke_mo_shi",      # 访客模式
    "input_boolean.master_bedroom_sleep", # 主卧舒眠
]

# ── Helper ───────────────────────────────────────────────────────────────


def find_homekit_entry():
    """Find the existing HomeKit Bridge config entry."""
    entries = api("GET", "/api/config/config_entries/entry")
    for entry in entries:
        if entry["domain"] == "homekit":
            return entry
    return None


def configure_homekit(entry_id):
    """Configure HomeKit Bridge via the options flow API."""
    # Step 1: Start options flow
    result = api("POST", "/api/config/config_entries/options/flow",
                 {"handler": entry_id})
    flow_id = result["flow_id"]
    print(f"  Options flow started: {flow_id}")

    # Step 2: Set mode=bridge, include mode, and make allowlisted domains
    # available in the entity picker.
    result = api("POST",
                 f"/api/config/config_entries/options/flow/{flow_id}",
                 {
                     "mode": "bridge",
                     "include_exclude_mode": "include",
                     "domains": INCLUDE_DOMAINS + SPECIFIC_ENTITY_DOMAINS,
                 })
    print(f"  Domains set: {', '.join(INCLUDE_DOMAINS + SPECIFIC_ENTITY_DOMAINS)}")

    # Step 3: Select specific entities to additionally include
    # (entities from light and media_player that we actually want)
    result = api("POST",
                 f"/api/config/config_entries/options/flow/{flow_id}",
                 {"entities": INCLUDE_ENTITIES})

    # Recent HA versions add an optional device-trigger step after the entity
    # filter. We only expose stateful entities, so keep that selection empty.
    if result.get("type") == "form" and result.get("step_id") == "bridged_device_triggers":
        result = api("POST",
                     f"/api/config/config_entries/options/flow/{flow_id}",
                     {"devices": []})

    if result.get("type") == "create_entry":
        print("  Options saved successfully")
        return True
    else:
        print(
            "  Unexpected options-flow result: "
            f"type={result.get('type')}, step_id={result.get('step_id')}"
        )
        return False


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    print("=== HomeKit Bridge 配置 ===\n")

    entry = find_homekit_entry()
    if not entry:
        print("[ERROR] HomeKit 集成未找到，请先在 HA UI 中添加 HomeKit 集成")
        return

    entry_id = entry["entry_id"]
    title = entry["title"]
    print(f"找到 HomeKit 集成: {title} ({entry_id})")

    # Show current state
    print(f"\n配置 HomeKit Bridge...")
    print(f"  包含域: {', '.join(INCLUDE_DOMAINS)}")
    print(f"  包含实体: {len(INCLUDE_ENTITIES)} 个")

    ok = configure_homekit(entry_id)

    if ok:
        print(f"\n[OK] HomeKit Bridge 配置完成")
        print(f"  - {len(INCLUDE_DOMAINS)} 个域全量包含")
        print(f"  - {len(INCLUDE_ENTITIES)} 个指定实体")
        print(f"  - Matter 设备已排除（通过 Matter 直连 HomeKit）")
        print(f"\n如需配对，请在 HA 设置 > 集成 > HomeKit 页面扫描二维码")
    else:
        print("\n[FAIL] 配置失败")


if __name__ == "__main__":
    main()
