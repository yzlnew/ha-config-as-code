"""Set up Claude Code usage monitoring in Home Assistant.

Creates:
- input_text.claude_code_usage_raw: stores raw webhook JSON
- Webhook automation: receives data and stores it
- Template sensors: five_hour / seven_day utilization + resets_at
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from ha_api import api, call_service, put_automation

# --- 1. Create input_text to store raw webhook data ---
print("Creating input_text.claude_code_usage_raw ...")
try:
    api("POST", "/api/services/input_text/reload", {})
except Exception:
    pass

# Check if already exists
try:
    state = api("GET", "/api/states/input_text.claude_code_usage_raw")
    print("  Already exists, skipping creation")
except Exception:
    # Need to create via config — input_text must be defined in YAML or created via helper API
    print("  Creating via helper API ...")
    try:
        # Use WebSocket-like REST endpoint for creating helpers
        api("POST", "/api/config/input_text", {
            "id": "claude_code_usage_raw",
            "name": "Claude Code Usage Raw",
            "min": 0,
            "max": 1000,
            "mode": "text",
            "icon": "mdi:cloud-percent",
        })
        print("  [OK] created input_text.claude_code_usage_raw")
    except Exception as e:
        print(f"  [WARN] Could not create via API: {e}")
        print("  You may need to create it manually in HA Settings > Helpers")

# --- 2. Create webhook automation ---
print("\nCreating webhook automation ...")
put_automation("claude_code_usage_webhook", {
    "alias": "Claude Code：接收用量数据",
    "description": "Receives Claude Code usage data via webhook and stores it in input_text",
    "mode": "single",
    "trigger": [
        {
            "trigger": "webhook",
            "webhook_id": "claude_code_usage",
            "allowed_methods": ["POST"],
            "local_only": True,
        }
    ],
    "condition": [],
    "action": [
        {
            "action": "input_text.set_value",
            "target": {"entity_id": "input_text.claude_code_usage_raw"},
            "data": {
                "value": "{{ trigger.json | to_json }}"
            },
        }
    ],
})

# --- 3. Create template sensors via REST API ---
print("\nCreating template sensors ...")

# We'll use trigger-based template sensors defined in the automation
# But first let's set an initial value so template sensors work
try:
    initial_data = {
        "five_hour_utilization": 0,
        "five_hour_resets_at": "",
        "seven_day_utilization": 0,
        "seven_day_resets_at": "",
        "extra_usage_enabled": False,
        "extra_usage_monthly_limit": 0,
        "extra_usage_used_credits": 0,
    }
    api("POST", "/api/services/input_text/set_value", {
        "entity_id": "input_text.claude_code_usage_raw",
        "value": json.dumps(initial_data),
    })
    print("  [OK] Set initial value")
except Exception as e:
    print(f"  [WARN] Could not set initial value: {e}")

print("\n--- Template Sensor YAML ---")
print("Add the following to your configuration.yaml (or a template sensors file):\n")

yaml_config = """
template:
  - trigger:
      - trigger: webhook
        webhook_id: claude_code_usage
        allowed_methods:
          - POST
        local_only: true
    sensor:
      - name: "Claude Code 5h 用量"
        unique_id: claude_code_five_hour_utilization
        state: "{{ trigger.json.five_hour_utilization | default(0) | round(1) }}"
        unit_of_measurement: "%"
        icon: mdi:clock-fast
        attributes:
          resets_at: "{{ trigger.json.five_hour_resets_at | default('') }}"
      - name: "Claude Code 7d 用量"
        unique_id: claude_code_seven_day_utilization
        state: "{{ trigger.json.seven_day_utilization | default(0) | round(1) }}"
        unit_of_measurement: "%"
        icon: mdi:calendar-week
        attributes:
          resets_at: "{{ trigger.json.seven_day_resets_at | default('') }}"
      - name: "Claude Code 额外用量"
        unique_id: claude_code_extra_usage
        state: "{{ trigger.json.extra_usage_used_credits | default(0) | round(2) }}"
        unit_of_measurement: "$"
        icon: mdi:currency-usd
        attributes:
          monthly_limit: "{{ trigger.json.extra_usage_monthly_limit | default(0) }}"
          enabled: "{{ trigger.json.extra_usage_enabled | default(false) }}"
"""

print(yaml_config)

print("=" * 60)
print("IMPORTANT: You need to add the template config above to HA.")
print("Then run the push script to send data:")
print("  /root/ha/scripts/push_claude_usage.sh")
print("=" * 60)
