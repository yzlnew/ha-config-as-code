# 用 Python + Claude Code 管理 Home Assistant：告别 YAML，拥抱 Configuration as Code

> 当你家里有 14 个智能墙壁开关、60+ 盏灯、多个窗帘电机、浴霸换气扇，还想让每个按键的单击/双击/长按都绑定不同功能时，你会怎么做？手动在 HA 界面里一个个点？还是去编辑那些让人头大的 YAML？

## 痛点：YAML 配置的困境

用过 Home Assistant 的人都知道，随着设备数量增长，配置管理会变成一场噩梦：

- **手动编辑易出错**：一个缩进错误就能让整个自动化失效，YAML 对空格敏感的特性让调试变得痛苦
- **不可复现**：通过 UI 创建的自动化散落在 `.storage/` 的 JSON 文件里，通过 YAML 配置的又在另一个地方，没有统一的来源
- **版本控制困难**：UI 创建的配置每次修改都会改变内部 ID，diff 几乎不可读
- **无法跨实例部署**：换了一台 HA 主机，所有配置都要从头来过
- **规模不经济**：当你需要为 14 个开关创建 27 条自动化时，逐个手动创建是不现实的

我最终决定换一种思路：**把 Home Assistant 当作基础设施来管理**。

## 核心理念：Configuration as Code

这个思路借鉴了 DevOps 领域的 Infrastructure as Code（IaC）——就像用 Terraform 管理云资源一样，我们用 Python 脚本通过 HA 的 API 来定义和部署所有配置。

**关键原则：**

1. **一切通过 API**：不手动编辑任何配置文件，所有变更通过 REST API 和 WebSocket API 完成
2. **脚本即文档**：Python 代码本身就是配置的单一来源（Single Source of Truth）
3. **幂等性**：脚本可以安全地重复执行，已存在的配置会被更新而非重复创建
4. **版本控制**：所有脚本纳入 Git 管理，每次变更可追溯

## 技术架构

### 1. 共享 API 客户端：`ha_api.py`

所有脚本共用一个 API 客户端，实现会话复用和统一的错误处理：

```python
"""Shared Home Assistant API client with connection reuse."""

import json, os, requests, urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HA_URL = os.getenv("HA_EXTERNAL_URL") or os.getenv("HA_URL")
TOKEN  = os.getenv("HA_TOKEN")

_session = None

def session():
    """Get or create a reusable requests.Session with HA auth."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        })
        _session.verify = False
        _session.timeout = 30
    return _session

def api(method, path, data=None):
    resp = session().request(method, f"{HA_URL}{path}", json=data, timeout=30)
    resp.raise_for_status()
    return resp.json()

def call_service(domain, service, data=None):
    return api("POST", f"/api/services/{domain}/{service}", data)

def put_automation(automation_id, config):
    try:
        api("POST", f"/api/config/automation/config/{automation_id}", config)
        print(f"  [OK] {automation_id}")
        return True
    except Exception as e:
        print(f"  [FAIL] {automation_id} -> {e}")
        return False
```

这个设计的好处：
- **会话复用**：所有请求共享同一个 TCP 连接，批量操作时性能显著提升
- **统一认证**：Token 从环境变量读取，脚本中不硬编码敏感信息
- **简洁接口**：`call_service()`、`put_automation()` 等高层函数让业务脚本更清晰

### 2. REST API 负责自动化、场景、服务调用

HA 的 Config API 支持通过 HTTP 直接创建和更新自动化：

```
POST /api/config/automation/config/{automation_id}  -> 创建/更新自动化
DELETE /api/config/automation/config/{automation_id} -> 删除自动化
POST /api/services/{domain}/{service}               -> 调用服务（reload 等）
```

### 3. WebSocket API 负责 Dashboard 部署和实体注册

有些操作只能通过 WebSocket 完成，比如更新实体的显示名称和图标：

```python
import websocket, ssl, json

ws_url = HA_URL.replace("https://", "wss://") + "/api/websocket"
ws = websocket.create_connection(ws_url, sslopt={"cert_reqs": ssl.CERT_NONE})

# 认证
ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))

# 更新实体注册表：设置中文名和图标
ws.send(json.dumps({
    "id": 1,
    "type": "config/entity_registry/update",
    "entity_id": "automation.btn_living_room_left_click",
    "name": "开关绑定：客厅灯光切换",
    "icon": "mdi:light-switch",
}))
```

这是因为 HA 的 REST API 创建自动化时不支持 `icon` 字段，必须通过 WebSocket 的 `config/entity_registry/update` 来设置。这种 API 边界的知识，正是 Claude Code Skills 擅长编码的领域知识。

### 4. 幂等设计

所有脚本都遵循幂等原则——运行一次和运行十次的结果完全相同：

- `put_automation()` 使用固定的 `automation_id`，存在则更新，不存在则创建
- 删除操作先检查是否存在，不存在则静默跳过
- 每次运行结束后自动 reload，确保变更生效

## 真实案例

### 案例一：一键部署 27 条无线开关自动化

我家有 14 个小米墙壁开关（单开/双开/三开），设置为无线模式后，每个按键支持单击、双击、长按三种动作。为 7 个区域的开关创建完整绑定，总共需要 27 条自动化。

核心思路是**数据驱动**——先定义开关元数据，然后用函数批量生成自动化配置：

```python
# 开关定义：设备 ID、类型、名称、区域
SWITCHES = [
    {"id": "2000365940", "type": "w3", "name": "入口开关", "area": "客厅",
     "mode_entities": [
         "select.xiaomi_cn_2000365940_w3_mode_p_2_2",  # 左键
         "select.xiaomi_cn_2000365940_w3_mode_p_3_2",  # 中键
         "select.xiaomi_cn_2000365940_w3_mode_p_4_2",  # 右键
     ]},
    # ... 还有 13 个开关
]

# 区域 -> 灯光实体映射
AREA_LIGHTS = {
    "客厅": ["light.intelligent_drive_power_supply_16", ...],  # 12 盏灯
    "西厨": ["light.chu_fang_deng_guang", ...],                # 9 盏灯
    # ... 共 7 个区域
}

# 智能切换：任意灯亮 -> 全关；全灭 -> 全开
def make_toggle_action(lights):
    lights_str = ", ".join(f"'{e}'" for e in lights)
    return [{
        "choose": [{
            "conditions": [{
                "condition": "template",
                "value_template": (
                    "{{ expand([" + lights_str + "]) "
                    "| selectattr('state','eq','on') | list | count > 0 }}"
                ),
            }],
            "sequence": [
                {"service": "light.turn_off", "target": {"entity_id": lights}},
            ],
        }],
        "default": [
            {"service": "light.turn_on", "target": {"entity_id": lights}},
        ],
    }]

# 批量注册自动化
add_auto("btn_living_room_left_click",
         "Btn: Living Room Light Toggle",
         "Living room left/key click -> toggle lights",
         triggers_for(lr_switches, "left", "click"),
         make_toggle_action(AREA_LIGHTS["客厅"]))
```

运行脚本的效果：

```
$ python setup_wireless_switches.py --bind

Step 3: Creating 27 button automations
============================================================
  [OK] btn_living_room_left_click
  [OK] btn_living_room_left_dblclick
  [OK] btn_living_room_left_longpress
  [OK] btn_living_room_middle_click
  ... (27 条全部成功)

Step 4: Setting Chinese display names & icons
============================================================
  [OK] automation.btn_living_room_left_click -> 开关绑定：客厅灯光切换
  [OK] automation.btn_living_room_left_dblclick -> 开关绑定：客厅灯带切换
  ...
```

如果手动在 UI 里做，这 27 条自动化 + 中文命名 + 图标设置至少需要 2 小时。用脚本？**30 秒**。

### 案例二：代码定义 Dashboard，支持 5 套主题切换

Dashboard 同样用 Python 脚本生成。我定义了 5 套视觉主题，通过修改一个变量即可切换整套 UI 风格：

```python
THEMES = {
    "md3_yellow":    { ... },  # MD3 柠黄 — Material You 暖黄色调
    "apple_home":    { ... },  # Apple Home — 简洁白底风格
    "cyber_scifi":   { ... },  # 赛博科幻 — 深色霓虹风格
    "minimal_dark":  { ... },  # 极简深色 — 低对比度暗色
    "warm_cabin":    { ... },  # 暖木小屋 — 木质纹理暖色调
}

ACTIVE_THEME = "md3_yellow"  # <- 改这一行切换全局主题
```

Dashboard 通过 WebSocket API 直接推送到 HA，无需重启，浏览器刷新即可生效。

### 案例三：每日宝可梦集成

一个有趣的小项目：每天根据日期算法从 PokeAPI 获取一只宝可梦，将中文名、属性、种族值、图鉴描述存入 HA 的 `input_text` helper，然后在 Dashboard 卡片上展示：

```python
from ha_api import call_service

def ha_set_input_text(entity_id, value):
    call_service("input_text", "set_value", {
        "entity_id": entity_id,
        "value": str(value)[:255],
    })

# 获取宝可梦数据并写入 HA
pokemon_data = json.dumps({
    "id": poke_id, "cn": name_cn, "en": name_en,
    "t": types_str, "hp": stats["hp"], ...
}, ensure_ascii=False)

ha_set_input_text("input_text.pokemon_data", pokemon_data)
ha_set_input_text("input_text.pokemon_sprite", sprite_url)
```

通过 HA 的自动化定时触发这个脚本，每天早上 Dashboard 上就会出现一只新的宝可梦。

### 案例四：Claude Code Skills 编码领域知识

Claude Code 的 Skills 功能让我们可以将 HA 管理的领域知识系统化。以下是我的 `home-assistant-manager` Skill 的结构：

```markdown
---
name: home-assistant-manager
description: Expert-level Home Assistant configuration management
  with deployment workflows, reload vs restart optimization,
  automation verification protocols, and dashboard management.
---

# Home Assistant Manager

## Core Capabilities
- Remote HA instance management via SSH and hass-cli
- Smart deployment workflows (git-based and rapid iteration)
- Automation testing and verification
- Reload vs restart optimization

## Reload vs Restart Decision Making

### Can be reloaded (fast, preferred):
- Automations: `hass-cli service call automation.reload`
- Scripts: `hass-cli service call script.reload`
- Scenes: `hass-cli service call scene.reload`
- Themes: `hass-cli service call frontend.reload_themes`

### Require full restart:
- Min/Max sensors and platform-based sensors
- New integrations in configuration.yaml
- Core configuration changes

## Automation Verification Workflow
1. Deploy via API
2. Check configuration: `ha core check`
3. Reload automations
4. Manually trigger to verify
5. Check logs for errors
6. Verify outcome (entity state, notification received, etc.)
```

有了这个 Skill，当你对 Claude Code 说"帮我创建一个自动化，当平板电量低于 60% 时开启充电插座"，它不仅能生成正确的代码，还知道：

- 自动化 ID 必须用纯 ASCII slug（拼音或英文），不能包含中文
- 创建后需要 reload 而非 restart
- 需要通过 WebSocket 额外设置图标
- 命名要遵循 `类别：具体描述` 的格式

**Claude Code 不只是代码生成器，它是一个编码了领域知识的运维助手。**

## 适用场景与局限性

### 最适合的场景

- **设备多、规则复杂的用户**：当你有几十上百个设备，手动配置的时间成本远高于写脚本
- **追求可复现的配置**：一键重建所有自动化、场景、Dashboard
- **多实例部署**：为不同住所部署相似但有差异的配置
- **团队协作**：多人维护同一套 HA 配置，Git 提供完整的变更审计

### 已知局限

- **需要 HA API 知识**：需要了解哪些功能走 REST API，哪些必须走 WebSocket
- **部分集成仍需 UI**：某些第三方集成（如 Matter、HomeKit）的初始设置必须通过 UI 完成
- **学习曲线**：对于只有几个设备的用户，投入产出比不高
- **API 变更风险**：HA 升级可能改变内部 API（虽然 Config API 相对稳定）

## 开源与总结

这套 Configuration as Code 的方案已经在我的家庭环境中稳定运行。核心文件结构如下：

```
ha-config-as-code/
├── ha_api.py                    # 共享 API 客户端
├── setup_wireless_switches.py   # 无线开关自动化（27 条）
├── setup_dashboard.py           # Dashboard 生成（5 套主题）
├── setup_automations.py         # 其他自动化
├── update_pokemon.py            # 每日宝可梦集成
├── .claude/
│   └── skills/
│       └── home-assistant-manager/
│           └── SKILL.md         # Claude Code 领域知识
└── .env                         # HA 连接信息（不入库）
```

**项目地址**：[https://github.com/yourname/ha-config-as-code](https://github.com/yourname/ha-config-as-code)

如果你也被 YAML 折磨过，或者想要一种更工程化的方式管理你的智能家居，欢迎尝试这套方案。Pull requests 和 Issues 都欢迎。

---

*用 Python 写代码，用 Claude Code 当运维，让 Home Assistant 真正成为可编程的智能家居平台。*
