# Home Assistant Configuration as Code

English version: [README.en.md](README.en.md)

通过 Python 脚本 + Home Assistant REST/WebSocket API，把自动化、场景、Dashboard 和设备配置以代码方式管理。

## 项目特点

- API First：主要通过 `/api/*` 和 `/api/websocket` 管理配置
- 幂等脚本：多数脚本可重复执行
- Git 版本化：所有改动可追踪、可回滚
- 结构化部署：按脚本分层管理（开关/场景/自动化/分组/Dashboard/集成）

## 当前目录结构

```text
ha/
├── README.md
├── README.en.md
├── TODO.md
├── .env.example
├── docs/
│   ├── blog-post-by-human.md
│   ├── blog-post.md
│   ├── ha-unicode-bug-report.md
│   ├── ha_family_manual_md3.html
│   └── matter-thread-offline-fix.md
├── esphome/
│   ├── trmnl_dashboard.yaml
│   ├── fonts/
│   └── images/
├── scripts/
│   ├── ha_api.py
│   ├── setup_wireless_switches.py
│   ├── setup_scenes.py
│   ├── setup_automations.py
│   ├── create_groups.py
│   ├── setup_dashboard.py
│   ├── setup_adaptive_lighting.py
│   ├── setup_homekit.py
│   ├── setup_power_on_state.py
│   ├── setup_weather_forecast.py
│   └── utils/
│       ├── ha_update_pokemon.py
│       ├── list_scenes.py
│       └── find_lock_entity.py
└── .claude/
    └── skills/
        └── interface-design/
```

## 环境变量

复制并编辑：

```bash
cp .env.example .env
```

`.env` 字段：

```env
HA_URL=http://YOUR_HA_IP:8123
HA_EXTERNAL_URL=https://your-domain.com:PORT
HA_TOKEN=your_long_lived_access_token
HA_SSH_HOST=YOUR_HA_IP
HA_SSH_USER=hassio
HA_SSH_PASSWORD=your_password
```

说明：

- `scripts/ha_api.py` 优先使用 `HA_EXTERNAL_URL`，否则回退 `HA_URL`
- `setup_weather_forecast.py` 依赖 SSH 变量写入 HA 配置文件

## 依赖

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install requests websocket-client urllib3 python-dotenv
```

额外依赖（仅 `setup_weather_forecast.py`）：

- 本机需要 `sshpass`
- HA 侧可通过 SSH + sudo 写入 `/homeassistant`

## 依赖的集成与插件

### HACS 集成

- [Adaptive Lighting](https://github.com/basnijholt/adaptive-lighting)：按区域配置自适应色温/亮度曲线，替代各平台自带的节律照明

### HACS 前端卡片

- [Mushroom](https://github.com/piitaya/lovelace-mushroom)：Dashboard 主要卡片组件
- [button-card](https://github.com/custom-cards/button-card)：自定义按钮样式
- [card-mod](https://github.com/thomasloven/lovelace-card-mod)：Shadow DOM CSS 注入，用于 Mushroom 等卡片的深度样式定制

### 官方 / 核心集成

- [Matter](https://www.home-assistant.io/integrations/matter/)：Matter 灯具接入
- [HomeKit Bridge](https://www.home-assistant.io/integrations/homekit/)：将非 Matter 设备暴露给 Apple Home
- [Xiaomi Miot Auto](https://github.com/al-one/hass-xiaomi-miot)：小米/米家设备接入（灯具、开关、传感器、浴霸等）
- [ESPHome](https://www.home-assistant.io/integrations/esphome/)：电子墨水屏等 ESP 设备接入

## 推荐执行顺序

```bash
# 1) 墙壁开关无线化（首次执行）
.venv/bin/python scripts/setup_wireless_switches.py --set-wireless

# 2) 清理旧自动化并绑定事件自动化
.venv/bin/python scripts/setup_wireless_switches.py --cleanup --bind

# 3) 场景
.venv/bin/python scripts/setup_scenes.py

# 4) 自动化与 helper
.venv/bin/python scripts/setup_automations.py

# 5) 灯光分组
.venv/bin/python scripts/create_groups.py

# 6) Dashboard（可选主题）
.venv/bin/python scripts/setup_dashboard.py --theme md3_yellow

# 7) Adaptive Lighting
.venv/bin/python scripts/setup_adaptive_lighting.py

# 8) HomeKit Bridge
.venv/bin/python scripts/setup_homekit.py

# 9) 设备上电状态
.venv/bin/python scripts/setup_power_on_state.py

# 10) 天气预报模板传感器（供 ESPHome 页面等使用）
.venv/bin/python scripts/setup_weather_forecast.py
```

## 脚本功能总览

### 核心 API

- `scripts/ha_api.py`：统一 REST 调用、认证与常用 helper（自动化/场景 upsert）

### 配置脚本

- `scripts/setup_wireless_switches.py`
  - `--set-wireless`：把开关按键设置为“无线开关”模式
  - `--cleanup`：删除旧 on/off 自动化
  - `--bind`：创建事件驱动的按键自动化并更新显示名称/icon
- `scripts/setup_scenes.py`：创建会客/影音/睡眠场景，重载场景并设置中文显示名称
- `scripts/setup_automations.py`：部署环境联动、安防、离家守护、宠物喂食、人来灯开等自动化，并补齐 input_boolean/counter helpers
- `scripts/create_groups.py`：创建分区灯组与全屋灯带组
- `scripts/setup_dashboard.py`：通过 WebSocket 覆盖写入 Lovelace 仪表盘
- `scripts/setup_adaptive_lighting.py`：按区域创建 Adaptive Lighting 实例
- `scripts/setup_homekit.py`：配置 HomeKit Bridge（排除 Matter 直连设备）
- `scripts/setup_power_on_state.py`：自动发现并设置灯具上电行为为“记忆/previous”
- `scripts/setup_weather_forecast.py`：写入模板传感器 YAML 并 reload，用于多日天气数据

### 工具脚本

- `scripts/utils/ha_update_pokemon.py`：每日宝可梦数据更新（适合 HA 容器内 shell_command 调用）
- `scripts/utils/list_scenes.py`：列出 `scene.*` 实体
- `scripts/utils/find_lock_entity.py`：按关键词检索门锁相关实体

## Dashboard 主题

`setup_dashboard.py` 当前支持：

- `md3_yellow`（默认）
- `apple_home`
- `tech_scifi`
- `minimal_dark`
- `warm_cabin`

示例：

```bash
.venv/bin/python scripts/setup_dashboard.py --theme apple_home
```

## ESPHome

- `esphome/trmnl_dashboard.yaml`：TRMNL（ESP32-S3）信息屏配置
- 依赖 HA 中的天气模板传感器（见 `setup_weather_forecast.py`）与多类实体数据
- 字体与像素图资源位于 `esphome/fonts/`、`esphome/images/`

## 说明

- 本仓库是具体家庭环境配置，实体 ID 与设备型号强相关
- 迁移到新环境时，优先修改各脚本中的实体映射常量
- 建议每次执行前后都提交 Git，便于快速 diff 与回滚
