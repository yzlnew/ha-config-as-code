# Matter over Thread 设备在 HA 中离线的排查与修复

## 问题现象

部分 Matter over Thread 灯在 Apple Home 中正常响应，但在 Home Assistant 中显示 unavailable。重启 Matter Server 无效。

## 环境

- HAOS 17.1，Proxmox VM（内核 6.12.67-haos）
- Matter Server v8.2.2
- 3 个 Apple Thread Border Router（1 Apple TV + 2 HomePod），Thread 1.3.0
- Thread 网络: `MyHome933860745`

## 根因 1：`accept_ra=0` 导致 HA 无法路由到 Thread 网格

### 原理

Thread 灯不在 WiFi 网络中，它们有独立的 IPv6 子网（Mesh-Local prefix）：

```
WiFi 网络                   Thread 网格
fd58:358d:2dcb::/64         fd8c:cc03:3d2f::/64（会变化）

  HA ◄──────── Border Router (Apple TV/HomePod) ────────► Thread 灯
  需要路由         同时连两个网络，通过 RA 广播路由           只在 Thread 中
```

Border Router 通过 **IPv6 Router Advertisement (RA)** 通知 WiFi 网络上的设备：
> "要访问 Thread mesh prefix，把包发给我"

但 HAOS 中 `forwarding=1`（Docker 需要），Linux 内核默认在开启转发时将 `accept_ra` 设为 0，导致 HA 忽略 Border Router 的 RA，拿不到 Thread mesh 的路由。

### 诊断

```bash
# SSH addon 中查看（只读，无法修改）
cat /proc/sys/net/ipv6/conf/enp6s18/accept_ra      # 0 = 问题所在
cat /proc/sys/net/ipv6/conf/enp6s18/forwarding      # 1 = 导致 accept_ra 被禁

# 验证路由是否正常（BusyBox 的 ip route show 可能不显示 dev，用 route get 更准确）
ip -6 route get fd8c:cc03:3d2f::1
# 正常: fd8c:cc03:3d2f::1 via fe80::xxxx dev enp6s18 ...
# 异常: 报错或没有 dev
```

> **注意**: Thread Mesh-Local prefix 不是固定的，会随 Thread 网络重建而改变（曾从 `fd8d:cdc4:6548::/64` 变为 `fd8c:cc03:3d2f::/64`）。

> **BusyBox 显示问题**: SSH addon 中 `ip -6 route show` 可能不显示 `dev enp6s18`，这是 BusyBox 精简版 ip 命令的显示 bug，不代表路由异常。用 `ip -6 route get <Thread地址>` 验证实际路由是否正常。

### ULA Prefix 对照

| Prefix | 用途 |
|--------|------|
| `fd58:358d:2dcb::/64` | 路由器分配的 ULA（HA 和 Border Router 共用） |
| `fdd5:98c1:66b6:45dc::/64` | Thread 网络 ULA |
| `fd8c:cc03:3d2f::/64` | Thread Mesh-Local（灯的实际地址，会变化） |
| `fd0c:ac1e:2100::/48` | HAOS Docker 内部网络 |

### 为什么设置静态 IPv6 不能解决？

静态 IPv6 只固定 HA 自己的地址，不解决路由问题。而且静态配置通常会禁用 RA 接收，反而更糟。

### 修复：设置 accept_ra=2

SSH addon 是容器，`/proc/sys` 只读。必须通过 HAOS host root shell 修改。

1. Proxmox Web UI → HAOS VM → **Console**
2. 输入 `login` 进入 root shell

```bash
# 立即生效
sysctl -w net.ipv6.conf.enp6s18.accept_ra=2
# 验证
cat /proc/sys/net/ipv6/conf/enp6s18/accept_ra  # 应显示 2
```

`accept_ra=2` 表示：即使 forwarding=1，也接受 RA 中的路由信息。

> **关于 `accept_ra_rt_info_max_plen`**: HAOS 6.12 内核未编译 `CONFIG_IPV6_ROUTE_INFO`，该 sysctl 不存在。实测仅 `accept_ra=2` 即可让路由正常工作。

#### 持久化（systemd service）

HAOS 的 `/etc/sysctl.d` 可能在重启后被重置，用 systemd service 更可靠：

```bash
cat > /etc/systemd/system/thread-fix.service << 'EOF'
[Unit]
Description=Fix accept_ra for Thread
After=network-online.target

[Service]
Type=oneshot
ExecStart=/sbin/sysctl -w net.ipv6.conf.enp6s18.accept_ra=2
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable thread-fix.service
```

## 根因 2：Border Router 路由卡死或 Matter Server 订阅过期

即使 `accept_ra=2` 已设置且路由正常（`ip -6 route get` 能解析），设备仍可能离线。此时 ping Thread mesh 地址 100% 丢包，说明问题在 Border Router 层面。

### 常见原因

- **Border Router 路由表卡死** — Apple TV/HomePod 长时间运行后，Thread Border Router 功能可能异常
- **Matter Server 订阅过期** — Matter 协议使用订阅机制保持通信，订阅过期后设备显示 unavailable（已知 6 小时周期性离线 bug）
- **Thread 网络 partition** — 部分设备与最近的 Border Router 失联

### 修复

1. **重启 Border Router** — 断电离线设备最近的 Apple TV 或 HomePod 约 30 秒，再通电
2. **重启 Matter Server** — HA → 设置 → 插件 → Matter Server → 重启
3. 等待 2-3 分钟让设备重新建立连接
4. 如果部分设备仍离线，**三个 Border Router 都重启一遍**

## 验证修复

```bash
# 在 HA API 中检查离线设备数量
curl -s -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/states" \
  | python3 -c "
import json, sys
states = json.load(sys.stdin)
for s in states:
    eid = s['entity_id']
    if eid.startswith('light.') and s['state'] == 'unavailable' \
       and ('moes' in eid or 'magical_homes' in eid or 'intelligent_drive' in eid):
        print(eid, '-', s['attributes'].get('friendly_name',''))
"
```

## 补充：Thread Preferred Network

HA Thread 集成中 `Preferred dataset: None`，意味着 HA 没有 Apple Thread 网络的凭据。

导入方式：iPhone HA Companion App → 设置 → Thread → 发送到 Home Assistant。

已知问题：可能报 "No preferred network found"，需先在 Mac 钥匙串访问中搜索 `MyHome`，删除旧的 Thread 条目后重试。

## 故障复发排查清单

设备再次离线时，按顺序排查：

1. **检查 `accept_ra`** — `cat /proc/sys/net/ipv6/conf/enp6s18/accept_ra` 应为 2
2. **验证路由** — `ip -6 route get <Thread mesh 地址>` 应有 `via ... dev enp6s18`
3. **ping Thread mesh** — `ping6 -c 2 fd8c:cc03:3d2f::1`，如果丢包说明 Border Router 问题
4. **重启 Border Router** — 断电最近的 HomePod/Apple TV
5. **重启 Matter Server** — HA 插件页面重启
6. **检查 Matter Server 版本** — 升级到最新版可缓解订阅过期 bug
7. **设备品牌差异** — Magical Homes 灯带离线率远高于 Intelligent Drive 射灯，可能与安装位置（灯槽遮挡信号）或固件质量有关
