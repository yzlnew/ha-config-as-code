#!/usr/bin/env python3
"""Configure the Aqara S1E panel and patch S1E2HA state feedback.

Run with environment loaded:
  set -a && source .env && set +a && .venv/bin/python scripts/setup_s1e_panel.py
"""

import json
import os
import socket
import sys
import time

import requests


S1E_HOST = os.getenv("S1E_HOST", "192.168.50.209")
S1E_TELNET_PORT = int(os.getenv("S1E_TELNET_PORT", "23"))
HA_URL = (os.getenv("HA_URL") or os.getenv("HA_EXTERNAL_URL") or "").rstrip("/")
HA_TOKEN = os.getenv("HA_TOKEN", "")
THEME_NAME = "书房中控·透明贴纸2"
THEME_TOPIC = "homeassistant/select/0x0054ef444fc2a8/theme"
S1E_THEME_DIR = "/data/theme/theme_908_1"
AQGUI_THEME_NAME = "theme_default_emoji"

SWITCH_CONFIG = {
    "restoreState": 1,
    "num": 3,
    "switchs": [
        {
            "id": 33,
            "enable": 1,
            "name": "空调",
            "icon": "air_conditioning",
            "wirelessName": "Switch1",
            "asWirelessSwitch": 1,
            "relayIndex": 0,
            "lastState": 0,
        },
        {
            "id": 34,
            "enable": 1,
            "name": "新风",
            "icon": "radiator_thermostat",
            "wirelessName": "Switch2",
            "asWirelessSwitch": 1,
            "relayIndex": 1,
            "lastState": 0,
        },
        {
            "id": 35,
            "enable": 1,
            "name": "桌面灯",
            "icon": "floor_lamp",
            "wirelessName": "Switch3",
            "asWirelessSwitch": 1,
            "relayIndex": 2,
            "lastState": 1,
        },
    ],
}

WIRELESS_BUTTON_CONFIG = {
    "num": 6,
    "switchs": [
        {"id": 129, "enable": 1, "name": "关其他灯", "iconId": "light_group"},
        {"id": 130, "enable": 1, "name": "空调", "iconId": "air_conditioning"},
        {"id": 131, "enable": 1, "name": "新风", "iconId": "radiator_thermostat"},
        {"id": 132, "enable": 1, "name": "桌面灯", "iconId": "floor_lamp"},
        {"id": 133, "enable": 1, "name": "灯光", "iconId": "ceiling_light"},
        {"id": 134, "enable": 1, "name": "场景", "iconId": "light_bulb"},
    ],
}


def shell_quote(value):
    return "'" + value.replace("'", "'\"'\"'") + "'"


def run_telnet(script):
    sock = socket.create_connection((S1E_HOST, S1E_TELNET_PORT), timeout=8)
    sock.settimeout(2)
    time.sleep(0.4)
    try:
        sock.recv(4096)
    except OSError:
        pass
    sock.sendall(b"root\n")
    time.sleep(0.3)
    try:
        sock.recv(4096)
    except OSError:
        pass

    sock.sendall((script + "\n").encode())
    out = b""
    deadline = time.time() + 35
    while time.time() < deadline:
        try:
            chunk = sock.recv(8192)
        except socket.timeout:
            continue
        if not chunk:
            break
        out += chunk
        if b"__END__" in out:
            break
    sock.close()
    return out.decode("utf-8", "ignore")


def sync_ha_theme_state():
    if not HA_URL or not HA_TOKEN:
        print("SKIP: HA_URL/HA_TOKEN not set; theme MQTT state was not synced.")
        return

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    })
    session.verify = False
    test = session.get(f"{HA_URL}/api/", timeout=10)
    test.raise_for_status()

    config = {
        "name": "主题",
        "uniq_id": "0x0054ef444fc2a8_theme",
        "~": THEME_TOPIC,
        "icon": "mdi:theme-light-dark",
        "options": [THEME_NAME],
        "avty_t": "~/status",
        "stat_t": "~/state",
        "cmd_t": "~/set",
        "send_cmd_t": "~/settheme",
        "json_attr_t": "~",
        "json_attr_tpl": "{{value_json.theme|tojson}}",
    }
    messages = [
        (f"{THEME_TOPIC}/config", json.dumps(config, ensure_ascii=False), True),
        (f"{THEME_TOPIC}/status", "online", True),
        (THEME_TOPIC, json.dumps({"theme": {"settheme": f"{THEME_TOPIC}/settheme"}}, ensure_ascii=False), True),
        (f"{THEME_TOPIC}/state", THEME_NAME, True),
    ]
    for topic, payload, retain in messages:
        resp = session.post(
            f"{HA_URL}/api/services/mqtt/publish",
            json={"topic": topic, "payload": payload, "retain": retain},
            timeout=10,
        )
        resp.raise_for_status()
    print(f"HA theme state synced: {THEME_NAME}")


def build_script():
    button_json = json.dumps(WIRELESS_BUTTON_CONFIG, ensure_ascii=False)
    return f"""
stty -echo
echo __BEGIN__
cp /data/bin/mqtt_sub.sh /data/bin/mqtt_sub.sh.codex.s1e.$(date +%Y%m%d%H%M%S)
awk '
/channel\\*\\)/ {{in_channel=1}}
/\\;\\;/ {{if (in_channel && seen_ret) {{in_channel=0; seen_ret=0}}}}
/channel_\\$\\{{id\\}}\\/state.*\\\"\\$msg\\\"/ {{next}}
{{print}}
in_channel && /ret=\\$\\(eval \\$cmd\\)/ {{print "                    [ -n \\"$id\\" ] && mqtt_pub \\"$HASS_PREFIX/switch/0x00${{DID}}/channel_${{id}}/state\\" \\"$msg\\""; seen_ret=1}}
' /data/bin/mqtt_sub.sh > /tmp/mqtt_sub.sh.s1e && mv /tmp/mqtt_sub.sh.s1e /data/bin/mqtt_sub.sh && chmod +x /data/bin/mqtt_sub.sh
if grep -q 'if \\[ -f "${{url##\\*/}}" \\]' /data/bin/mqtt_sub.sh; then
  sed -i 's#if \\[ -f "${{url##\\*/}}" \\]#if [ -f "/tmp/${{url##*/}}" ]#' /data/bin/mqtt_sub.sh
fi
cp /data/bin/ubus_monitor.sh /data/bin/ubus_monitor.sh.codex.s1e.$(date +%Y%m%d%H%M%S)
if ! grep -q 'switch/0x00${{DID}}/channel_${{id}}/state' /data/bin/ubus_monitor.sh; then
  awk '
  /if \\[ \\$id != 1 -a \\$id != 2 -a \\$id != 3 \\]; then/ && !inserted {{
    print "        if [ $id = 1 -o $id = 2 -o $id = 3 ]; then"
    print "            topic=\\"$HASS_PREFIX/switch/0x00${{DID}}/channel_${{id}}/state\\""
    print "            state=$(echo $data | jshon -Q -e state)"
    print "            [ \\"x$state\\" == \\"x1\\" ] && msg=\\"ON\\" || msg=\\"OFF\\""
    print "            mqtt_pub \\"$topic\\" \\"$msg\\""
    print "            return"
    print "        fi"
    inserted=1
  }}
  {{ print }}
  ' /data/bin/ubus_monitor.sh > /tmp/ubus_monitor.sh.s1e && mv /tmp/ubus_monitor.sh.s1e /data/bin/ubus_monitor.sh && chmod +x /data/bin/ubus_monitor.sh
fi
umount /usr/share/aqgui/theme 2>/dev/null || true
umount /usr/share/aqgui/theme/{AQGUI_THEME_NAME}/homepage 2>/dev/null || true
umount /usr/share/aqgui/theme/{AQGUI_THEME_NAME}/preview 2>/dev/null || true
mount --bind {S1E_THEME_DIR}/homepage /usr/share/aqgui/theme/{AQGUI_THEME_NAME}/homepage 2>/dev/null || true
mount --bind {S1E_THEME_DIR}/preview /usr/share/aqgui/theme/{AQGUI_THEME_NAME}/preview 2>/dev/null || true
current_switch_state=$(ubus -S call switch state)
state1=$(echo "$current_switch_state" | jshon -e switchs -e 0 -e state)
state2=$(echo "$current_switch_state" | jshon -e switchs -e 1 -e state)
state3=$(echo "$current_switch_state" | jshon -e switchs -e 2 -e state)
[ -z "$state1" ] && state1=0
[ -z "$state2" ] && state2=0
[ -z "$state3" ] && state3=0
switch_config="{{\\"restoreState\\":1,\\"num\\":3,\\"switchs\\":[{{\\"id\\":33,\\"enable\\":1,\\"name\\":\\"空调\\",\\"icon\\":\\"air_conditioning\\",\\"wirelessName\\":\\"Switch1\\",\\"asWirelessSwitch\\":1,\\"relayIndex\\":0,\\"lastState\\":$state1}},{{\\"id\\":34,\\"enable\\":1,\\"name\\":\\"新风\\",\\"icon\\":\\"radiator_thermostat\\",\\"wirelessName\\":\\"Switch2\\",\\"asWirelessSwitch\\":1,\\"relayIndex\\":1,\\"lastState\\":$state2}},{{\\"id\\":35,\\"enable\\":1,\\"name\\":\\"桌面灯\\",\\"icon\\":\\"floor_lamp\\",\\"wirelessName\\":\\"Switch3\\",\\"asWirelessSwitch\\":1,\\"relayIndex\\":2,\\"lastState\\":$state3}}]}}"
ubus -S call switch set.config "$switch_config"
ubus -S call switch set.wconfig {shell_quote(button_json)}
for i in 0 1 2; do
  id=$(echo "$current_switch_state" | jshon -e switchs -e $i -e id)
  state=$(echo "$current_switch_state" | jshon -e switchs -e $i -e state)
  [ -n "$id" ] && [ -n "$state" ] && ubus -S call switch set.state "{{\\"id\\":$id,\\"state\\":$state}}" >/dev/null 2>&1 || true
done
for p in $(pgrep -f '/data/bin/mqtt_sub.sh'); do kill -9 $p 2>/dev/null || true; done
for p in $(pgrep -f '/data/bin/ubus_monitor.sh'); do kill -9 $p 2>/dev/null || true; done
for p in $(pgrep -f '/data/bin/res_monitor.sh'); do kill -9 $p 2>/dev/null || true; done
for p in $(pgrep -f 'mosquitto_sub.*0x0054ef444fc2a8'); do kill -9 $p 2>/dev/null || true; done
sleep 1
/data/bin/run_s1e2ha.sh >/tmp/s1e2ha.restart.log 2>&1 &
sleep 5
DID=$(ubus -S call setting product.info | jshon -e did | tr -d '"')
MQTT_IP=$(grep MQTT_IP /data/etc/mqtt.conf | cut -d= -f2 | tr -d '"')
MQTT_USER=$(grep MQTT_USER /data/etc/mqtt.conf | cut -d= -f2 | tr -d '"')
MQTT_PASSWORD=$(grep MQTT_PASSWORD /data/etc/mqtt.conf | cut -d= -f2 | tr -d '"')
MQTT_PORT=$(grep MQTT_PORT /data/etc/mqtt.conf | cut -d= -f2 | tr -d '"')
current_switch_state=$(ubus -S call switch state)
for i in 0 1 2; do
  id=$(echo "$current_switch_state" | jshon -e switchs -e $i -e id)
  state=$(echo "$current_switch_state" | jshon -e switchs -e $i -e state)
  [ "x$state" = "x1" ] && msg=ON || msg=OFF
  [ -n "$id" ] && /bin/mosquitto_pub -h "$MQTT_IP" -u "$MQTT_USER" -P "$MQTT_PASSWORD" -p "$MQTT_PORT" -t "homeassistant/switch/0x00${{DID}}/channel_${{id}}/state" -m "$msg"
done
ubus -S call page set.theme '{{"themeName":"{AQGUI_THEME_NAME}"}}' >/dev/null 2>&1 || true
uci set setting.theme.name='{AQGUI_THEME_NAME}'
uci commit setting
killall -9 aqgui 2>/dev/null || true
sleep 2
app_start.sh -g >/dev/null 2>&1 || true
sleep 4
echo '# processes'
pgrep -fl 'mqtt_sub|ubus_monitor|res_monitor|mosquitto_sub|aqgui' || true
echo '# page theme'
ubus -S call page get.theme 2>/dev/null || true
echo '# switch state'
ubus -S call switch state
echo '# switch config'
ubus -S call switch get.config
echo '# wireless config'
ubus -S call switch get.wconfig
echo __END__
"""


def main():
    if not S1E_HOST:
        print("ERROR: S1E_HOST is required", file=sys.stderr)
        return 1
    print(run_telnet(build_script()))
    sync_ha_theme_state()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
