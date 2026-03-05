# Home Assistant Automation TODO List

## Planned Automations
- [x] **Leave Home "Full Off"**: Automatically turn off all lights, climate, and media players when the smart lock is locked (handle lifted) and no presence is detected for 10 minutes. Send notification to iPhone18,2.
- [ ] **Climate Intelligence**:
    - [ ] Fresh air/purifier auto-management based on PM2.5/CO₂.
    - [ ] AC energy saving (auto-off when windows open).
    - [x] Bathroom dehumidification (auto-ventilation based on humidity, presence-aware).
- [ ] **Presence & Lighting**:
    - [x] Welcome Home mode (lock opened + low light → 会客场景).
    - [x] Presence-based lighting (人来灯开/人走灯灭): 主卧、主卫、次卧、次卫，优先独立传感器。
    - [ ] Night-light mode (dim lights during early hours for bathroom trips).
- [ ] **Safety & Care**:
    - [ ] Extreme weather protection (close curtains on wind/rain).
    - [x] Water leak emergency (flashing red lights + notifications).
    - [x] Battery low-level notifications (门锁/温湿度计×2/水浸卫士/饮水机 → 推送+换电池待办).
- [x] **Advanced Switch Logic**:
    - [x] Long-press for area "Full Off".
    - [x] Double-click for strip/curtain toggle.
- [x] **PetKit Automations**:
    - [x] Nova 如厕通知 (猫厕所占用 → iPhone 推送).
    - [x] Nova 喝水通知 (饮水次数变化 → iPhone 推送).
    - [x] 缺猫砂通知 (猫砂不足 → iPhone 推送 + 购物清单待办).
    - [x] 垃圾箱已满通知 (垃圾箱满 → iPhone 推送 + 购物清单待办).

- [x] **Laundry Notifications**:
    - [x] 洗衣机/烘干机/洗碗机完成 → iPhone 推送 + HomePod 语音播报.
- [ ] **Scene Auto-Recovery**:
    - [ ] 影音模式自动恢复：电视关闭后自动关闭影音模式（开灯+开窗帘）.
    - [ ] 会客模式定时关闭：深夜 23:00 后自动降为夜灯亮度.
- [ ] **Curtain Automation**:
    - [ ] 日出自动开窗帘（工作日 + 休息日可设不同时间）.
    - [ ] 日落自动关窗帘.
    - [ ] 晾衣架遇雨自动收回（天气集成检测降雨）.
- [ ] **Cat Health Monitor**:
    - [ ] Nova 体重异常波动告警（±0.3kg 短期变化）.
    - [ ] Nova 超过 24h 未如厕 → 健康提醒推送.
    - [ ] Nova 日饮水为 0 → 晚间提醒关注饮水.
- [ ] **Morning Routine**:
    - [ ] 工作日起床模式：闹钟时间 → 开窗帘 + 灯光渐亮 + 音箱播报天气.
- [ ] **Air Quality Auto-Management**:
    - [ ] PM2.5 > 75 自动开启净化器，< 35 自动关闭.
    - [ ] CO₂ > 1000 自动开启新风机，< 600 自动关闭.
- [ ] **Comfort & Energy**:
    - [ ] 室内温度过高/过低 → 推送提醒开空调.
    - [ ] 空气净化器/新风机滤芯到期 → 推送 + 购物清单待办.
- [ ] **Security & Away**:
    - [ ] 离家模拟在家：外出超过 2 小时后，随机开关灯模拟有人.
    - [ ] 门锁异常告警：连续输错密码 / 未授权开锁 → 紧急推送.

## Dashboard & UI
- [x] **Integrated Machine Panels**:
    - [x] Dishwasher: MD3 style with program selector and status-aware icon.
    - [x] Washer/Dryer: Real-time badges (Power, Water, Energy) in top-right.
    - [x] Conditional Layout: Simplified view for inactive devices, full dashboard for active ones.
    - [x] UI Polish: Remove redundant shadows, optimize select components for MD3 "Filled" look.
- [x] **PetKit Dashboard Tab**:
    - [x] Nova profile (avatar, weight graph, last usage).
    - [x] 猫厕所MAX panel (status, alerts, action buttons, maintenance, switches).
    - [x] 饮水机MAX panel (battery/filter graphs, drink count).
