#!/usr/bin/env python3
"""Create trigger-based template sensors for multi-day weather forecast.

ESPHome cannot call weather.get_forecasts directly, so we create
trigger-based template sensors in HA that refresh every 30 minutes.

This script:
1. Uploads a template sensor config file to HA via SCP
2. Adds !include_dir_merge_list to configuration.yaml if not present
3. Reloads template entities
"""

import json
import os
import ssl
import subprocess
import sys

import websocket

sys.path.insert(0, os.path.dirname(__file__))
from ha_api import HA_URL, TOKEN

CONFIG_DIR = "/homeassistant"

TEMPLATE_YAML = """\
# Weather forecast template sensors - managed by setup_weather_forecast.py
- trigger:
    - platform: time_pattern
      minutes: "/30"
    - platform: homeassistant
      event: start
  action:
    - service: weather.get_forecasts
      target:
        entity_id: weather.forecast_wo_de_jia
      data:
        type: daily
      response_variable: forecast
  sensor:
    - name: "Tomorrow Weather Condition"
      unique_id: tomorrow_weather_condition
      state: "{{ forecast['weather.forecast_wo_de_jia'].forecast[0].condition | default('unknown') }}"

    - name: "Tomorrow Weather Temp High"
      unique_id: tomorrow_weather_temp_high
      state: "{{ forecast['weather.forecast_wo_de_jia'].forecast[0].temperature | default(0) }}"
      unit_of_measurement: "°C"
      device_class: temperature
      state_class: measurement

    - name: "Tomorrow Weather Temp Low"
      unique_id: tomorrow_weather_temp_low
      state: "{{ forecast['weather.forecast_wo_de_jia'].forecast[0].templow | default(0) }}"
      unit_of_measurement: "°C"
      device_class: temperature
      state_class: measurement

    - name: "Day After Weather Condition"
      unique_id: day_after_weather_condition
      state: "{{ forecast['weather.forecast_wo_de_jia'].forecast[1].condition | default('unknown') }}"

    - name: "Day After Weather Temp High"
      unique_id: day_after_weather_temp_high
      state: "{{ forecast['weather.forecast_wo_de_jia'].forecast[1].temperature | default(0) }}"
      unit_of_measurement: "°C"
      device_class: temperature
      state_class: measurement

    - name: "Day After Weather Temp Low"
      unique_id: day_after_weather_temp_low
      state: "{{ forecast['weather.forecast_wo_de_jia'].forecast[1].templow | default(0) }}"
      unit_of_measurement: "°C"
      device_class: temperature
      state_class: measurement
"""


def ssh_cmd(cmd, input_data=None):
    """Run a command on HA via SSH (with sudo)."""
    host = os.getenv("HA_SSH_HOST")
    user = os.getenv("HA_SSH_USER")
    password = os.getenv("HA_SSH_PASSWORD")
    full_cmd = [
        "sshpass", "-p", password,
        "ssh", "-o", "StrictHostKeyChecking=no",
        f"{user}@{host}", f"sudo sh -c '{cmd}'"
    ]
    result = subprocess.run(full_cmd, capture_output=True, text=True, input=input_data)
    if result.returncode != 0 and result.stderr.strip():
        print(f"  SSH error: {result.stderr.strip()}")
    return result


def ssh_write_file(remote_path, content):
    """Write file content to HA via SSH stdin pipe."""
    host = os.getenv("HA_SSH_HOST")
    user = os.getenv("HA_SSH_USER")
    password = os.getenv("HA_SSH_PASSWORD")
    full_cmd = [
        "sshpass", "-p", password,
        "ssh", "-o", "StrictHostKeyChecking=no",
        f"{user}@{host}",
        f"sudo tee {remote_path} > /dev/null"
    ]
    result = subprocess.run(full_cmd, capture_output=True, text=True, input=content)
    if result.returncode != 0 and result.stderr.strip():
        print(f"  SSH error: {result.stderr.strip()}")
    return result


def main():
    print("=== Weather Forecast Template Sensors Setup ===\n")

    # Step 1: Create templates directory
    print("1. Creating templates directory...")
    ssh_cmd(f"mkdir -p {CONFIG_DIR}/templates")

    # Step 2: Write template config via stdin pipe (avoids shell escaping with Jinja)
    print("2. Writing weather forecast template config...")
    result = ssh_write_file(f"{CONFIG_DIR}/templates/weather_forecast.yaml", TEMPLATE_YAML)
    if result.returncode != 0:
        print("  ERROR: Failed to write template config!")
        sys.exit(1)

    # Verify
    result = ssh_cmd(f"head -3 {CONFIG_DIR}/templates/weather_forecast.yaml")
    if "trigger" not in result.stdout:
        print("  ERROR: File verification failed!")
        print(f"  stdout: {result.stdout}")
        sys.exit(1)
    print("  OK - template config written")

    # Step 3: Add template include to configuration.yaml if needed
    print("3. Checking configuration.yaml for template include...")
    result = ssh_cmd(f"grep include_dir_merge_list {CONFIG_DIR}/configuration.yaml")
    if "include_dir_merge_list" not in result.stdout:
        print("  Adding template include to configuration.yaml...")
        ssh_cmd(f"printf \"\\ntemplate: !include_dir_merge_list templates/\\n\" >> {CONFIG_DIR}/configuration.yaml")
        print("  OK - added template: !include_dir_merge_list templates/")
    else:
        print("  Already present, skipping")

    # Step 4: Verify configuration
    print("4. Verifying configuration...")
    result = ssh_cmd(f"grep template: {CONFIG_DIR}/configuration.yaml")
    print(f"  Config line: {result.stdout.strip()}")

    # Step 5: Reload via WebSocket
    print("5. Reloading template entities via WebSocket...")
    ws_url = HA_URL.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"

    ws = websocket.create_connection(
        ws_url, timeout=15,
        sslopt={"cert_reqs": ssl.CERT_NONE} if "wss://" in ws_url else {}
    )

    # Auth
    msg = json.loads(ws.recv())
    ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
    msg = json.loads(ws.recv())
    if msg["type"] != "auth_ok":
        print(f"  Auth failed: {msg}")
        ws.close()
        sys.exit(1)
    print("  Authenticated")

    # Call reload - template entities use homeassistant.reload_all
    ws.send(json.dumps({
        "id": 1,
        "type": "call_service",
        "domain": "homeassistant",
        "service": "reload_all",
    }))
    msg = json.loads(ws.recv())
    print(f"  Reload result: success={msg.get('success')}")

    if not msg.get("success"):
        print(f"  Error: {msg.get('error', {})}")
        print("\n  NOTE: If reload fails, try restarting HA:")
        print("  Developer Tools > YAML > Check & Restart")

    ws.close()

    print("\n=== Done! ===")
    print("Template sensors created:")
    print("  - sensor.tomorrow_weather_condition")
    print("  - sensor.tomorrow_weather_temp_high")
    print("  - sensor.tomorrow_weather_temp_low")
    print("  - sensor.day_after_weather_condition")
    print("  - sensor.day_after_weather_temp_high")
    print("  - sensor.day_after_weather_temp_low")
    print("\nCheck Developer Tools > States to verify they have data.")
    print("(May take up to 30 min for first trigger, or restart HA)")


if __name__ == "__main__":
    main()
