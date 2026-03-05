# Home Assistant

- HA 连接信息: 在项目根目录 `.env` 文件中配置（参考 `.env.example`）
- SSH: `sshpass -p "$HA_SSH_PASSWORD" ssh -o StrictHostKeyChecking=no $HA_SSH_USER@$HA_SSH_HOST`
- SSH 执行 ha CLI 需加载 token: `SUPERVISOR_TOKEN=$(cat /run/s6/container_environment/SUPERVISOR_TOKEN) ha <command>`
- Python 环境: 使用项目根目录的 `.venv` 虚拟环境运行 Python 脚本（`.venv/bin/python`）
- 运行 Python 脚本前必须用 `set -a && source .env && set +a` 加载环境变量（`set -a` 确保变量被 export 到子进程，仅 `source .env` 不会 export）

## API 访问

- 调用 HA API 前，先用简单的 test call 验证 token 有效性。本地 URL 报错时改用外部 URL + SSL。同一认证方式最多尝试 2 次，失败后询问用户。
- 生成 automation ID、entity ID 等标识符时，必须使用纯 ASCII slug（拼音或英文）。禁止在 ID、API 传入的文件名、含 JSON 花括号的 format string 中使用中文。

## WebSocket API

以下操作 REST API 不支持，必须通过 WebSocket 完成：

- **设置 entity 的 icon / 显示名**: `config/entity_registry/update`（REST automation config API 不支持 icon 字段）
- **修改设备所属区域**: `config/device_registry/update`，参数 `device_id` + `area_id`
- **获取区域/设备/实体列表**: `config/area_registry/list`、`config/device_registry/list`、`config/entity_registry/list`

## 自动化规范

- 命名格式: `类别：具体描述`，如 `自动充电：平板电量低于60开启`
- 必须设置 icon（通过 WebSocket `config/entity_registry/update`）

## Dashboard

- Mushroom 等自定义卡片使用 shadow DOM，标准 CSS 覆盖无效。使用 card-mod + shadow DOM 选择器，或选用支持直接样式的卡片类型。
