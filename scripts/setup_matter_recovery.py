#!/usr/bin/env python3
"""Deploy Matter light recovery support to Home Assistant and OpenWrt.

This sets up:
- A Home Assistant template sensor for Matter light offline count.
- A Home Assistant shell_command that asks OpenWrt to restart networking.
- A narrow OpenWrt rpcd ACL + helper script for that network restart.
"""

import json
import os
import shlex
import subprocess
import sys
import time
import urllib.request

from ha_api import call_service

HA_CONFIG_DIR = "/homeassistant"
HA_SHELL_COMMAND = '  matter_restart_router_network: "python3 /config/scripts/matter_router_recovery.py"'

MATTER_LIGHT_PATTERN = (
    "intelligent_drive_power_supply|intelligent_power|"
    "magical_homes_color_light|moes_matter_light"
)

TEMPLATE_YAML = f"""\
# Matter light recovery sensors - managed by setup_matter_recovery.py
- sensor:
    - name: "matter_light_offline_count"
      unique_id: matter_light_offline_count
      icon: mdi:lightbulb-alert
      state_class: measurement
      state: >-
        {{% set ns = namespace(count=0) %}}
        {{% for entity in states.light if entity.entity_id is search('{MATTER_LIGHT_PATTERN}') %}}
          {{% if entity.state in ['unavailable', 'unknown'] %}}
            {{% set ns.count = ns.count + 1 %}}
          {{% endif %}}
        {{% endfor %}}
        {{{{ ns.count }}}}
      attributes:
        total: >-
          {{{{ states.light | selectattr('entity_id', 'search', '{MATTER_LIGHT_PATTERN}') | list | count }}}}
        offline_entities: >-
          {{% set ns = namespace(items=[]) %}}
          {{% for entity in states.light if entity.entity_id is search('{MATTER_LIGHT_PATTERN}') %}}
            {{% if entity.state in ['unavailable', 'unknown'] %}}
              {{% set ns.items = ns.items + [entity.entity_id] %}}
            {{% endif %}}
          {{% endfor %}}
          {{{{ ns.items }}}}
        offline_names: >-
          {{% set ns = namespace(items=[]) %}}
          {{% for entity in states.light if entity.entity_id is search('{MATTER_LIGHT_PATTERN}') %}}
            {{% if entity.state in ['unavailable', 'unknown'] %}}
              {{% set ns.items = ns.items + [entity.attributes.friendly_name | default(entity.entity_id, true)] %}}
            {{% endif %}}
          {{% endfor %}}
          {{{{ ns.items }}}}
"""

ROUTER_HELPER_SH = """\
#!/bin/sh
if [ "$1" = "--dry-run" ]; then
  echo "ha-matter-recovery-ok"
  exit 0
fi

(
  sleep 1
  /etc/init.d/network restart
) >/tmp/ha-matter-recovery-network.log 2>&1 &

echo "scheduled network restart"
exit 0
"""

ROUTER_ACL_JSON = """\
{
  "ha-matter-recovery": {
    "description": "Allow Home Assistant to restart networking for Matter recovery",
    "write": {
      "ubus": {
        "file": [ "exec" ]
      },
      "file": {
        "/usr/bin/ha-matter-recovery-network-restart": [ "exec" ],
        "/usr/bin/ha-matter-recovery-network-restart --dry-run": [ "exec" ]
      }
    }
  }
}
"""

HA_RECOVERY_PY = """\
#!/usr/bin/env python3
import json
import sys
import urllib.request

CONFIG_PATH = "/config/.matter_recovery.json"


def ubus_call(endpoint, payload, timeout=12):
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def main():
    dry_run = "--dry-run" in sys.argv

    with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
        config = json.load(handle)

    endpoint = config.get("openwrt_ubus_url", "http://192.168.50.1/ubus")
    username = config.get("openwrt_username", "root")
    password = config["openwrt_password"]

    login = ubus_call(endpoint, {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "call",
        "params": [
            "00000000000000000000000000000000",
            "session",
            "login",
            {"username": username, "password": password},
        ],
    })
    if login.get("result", [1])[0] != 0:
        raise SystemExit(f"OpenWrt login failed: {login}")

    session_id = login["result"][1]["ubus_rpc_session"]
    result = ubus_call(endpoint, {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "call",
        "params": [
            session_id,
            "file",
            "exec",
            {
                "command": "/usr/bin/ha-matter-recovery-network-restart",
                "params": ["--dry-run"] if dry_run else [],
            },
        ],
    })
    if result.get("result", [1])[0] != 0:
        raise SystemExit(f"OpenWrt network restart trigger failed: {result}")
    print("OpenWrt network restart dry-run OK" if dry_run else "OpenWrt network restart scheduled")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"matter_router_recovery failed: {exc}", file=sys.stderr)
        raise
"""


def require_env(name):
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def run(cmd, input_data=None):
    result = subprocess.run(cmd, input=input_data, capture_output=True, text=True)
    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(f"Command failed: {' '.join(shlex.quote(part) for part in cmd)}")
    return result


def ha_ssh_args():
    return [
        "sshpass", "-p", require_env("HA_SSH_PASSWORD"),
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=8",
        f"{require_env('HA_SSH_USER')}@{require_env('HA_SSH_HOST')}",
    ]


def router_ssh_args():
    router_host = os.getenv("ROUTER_HOST", "192.168.50.1")
    router_user = os.getenv("ROUTER_USER", "root")
    router_password = (
        os.getenv("ROUTER_PASSWORD")
        or os.getenv("OPENWRT_PASSWORD")
        or os.getenv("ROUTER_SSH_PASSWORD")
        or os.getenv("HA_SSH_PASSWORD")
    )
    if not router_password:
        raise SystemExit("Missing ROUTER_PASSWORD/OPENWRT_PASSWORD/ROUTER_SSH_PASSWORD")
    return [
        "sshpass", "-p", router_password,
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=8",
        f"{router_user}@{router_host}",
    ]


def ha_write(path, content, mode="0644"):
    quoted = shlex.quote(path)
    run(ha_ssh_args() + [f"sudo tee {quoted} >/dev/null && sudo chmod {mode} {quoted}"], input_data=content)


def router_write(path, content, mode="0644"):
    quoted = shlex.quote(path)
    run(router_ssh_args() + [f"cat > {quoted} && chmod {mode} {quoted}"], input_data=content)


def ha_read(path):
    return run(ha_ssh_args() + [f"sudo cat {shlex.quote(path)}"]).stdout


def ensure_shell_command(config):
    if "matter_restart_router_network:" in config:
        return config

    lines = config.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "shell_command:" and not line.startswith(" "):
            lines.insert(index + 1, HA_SHELL_COMMAND)
            return "\n".join(lines) + "\n"

    if config and not config.endswith("\n"):
        config += "\n"
    return config + "\nshell_command:\n" + HA_SHELL_COMMAND + "\n"


def verify_router_ubus():
    router_host = os.getenv("ROUTER_HOST", "192.168.50.1")
    router_user = os.getenv("ROUTER_USER", "root")
    router_password = (
        os.getenv("ROUTER_PASSWORD")
        or os.getenv("OPENWRT_PASSWORD")
        or os.getenv("ROUTER_SSH_PASSWORD")
        or os.getenv("HA_SSH_PASSWORD")
    )
    endpoint = f"http://{router_host}/ubus"

    def call(payload):
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            return json.load(response)

    login = None
    for _ in range(8):
        try:
            login = call({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "call",
                "params": [
                    "00000000000000000000000000000000",
                    "session",
                    "login",
                    {"username": router_user, "password": router_password},
                ],
            })
            if login.get("result", [1])[0] == 0:
                break
        except Exception:
            login = None
        time.sleep(1)
    if not login or login.get("result", [1])[0] != 0:
        raise SystemExit(f"OpenWrt ubus login verification failed: {login}")
    session_id = login["result"][1]["ubus_rpc_session"]
    result = call({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "call",
        "params": [
            session_id,
            "file",
            "exec",
            {"command": "/usr/bin/ha-matter-recovery-network-restart", "params": ["--dry-run"]},
        ],
    })
    if result.get("result", [1])[0] != 0:
        raise SystemExit(f"OpenWrt ubus dry-run failed: {result}")
    print("  OpenWrt ubus dry-run OK")


def main():
    print("=== Matter Recovery Setup ===")

    router_host = os.getenv("ROUTER_HOST", "192.168.50.1")
    router_user = os.getenv("ROUTER_USER", "root")
    router_password = (
        os.getenv("ROUTER_PASSWORD")
        or os.getenv("OPENWRT_PASSWORD")
        or os.getenv("ROUTER_SSH_PASSWORD")
        or os.getenv("HA_SSH_PASSWORD")
    )
    if not router_password:
        raise SystemExit("Missing router password env var")

    print("1. Installing OpenWrt rpcd helper...")
    router_write("/usr/bin/ha-matter-recovery-network-restart", ROUTER_HELPER_SH, "0755")
    router_write("/usr/share/rpcd/acl.d/ha-matter-recovery.json", ROUTER_ACL_JSON, "0644")
    run(router_ssh_args() + ["/etc/init.d/rpcd restart"])
    verify_router_ubus()

    print("2. Installing Home Assistant recovery files...")
    ha_write(f"{HA_CONFIG_DIR}/scripts/matter_router_recovery.py", HA_RECOVERY_PY, "0755")
    ha_write(f"{HA_CONFIG_DIR}/templates/matter_lights.yaml", TEMPLATE_YAML, "0644")
    ha_write(
        f"{HA_CONFIG_DIR}/.matter_recovery.json",
        json.dumps({
            "openwrt_ubus_url": f"http://{router_host}/ubus",
            "openwrt_username": router_user,
            "openwrt_password": router_password,
        }, indent=2) + "\n",
        "0644",
    )

    print("3. Ensuring shell_command is configured...")
    config_path = f"{HA_CONFIG_DIR}/configuration.yaml"
    current = ha_read(config_path)
    updated = ensure_shell_command(current)
    if updated != current:
        ha_write(config_path, updated, "0644")
        print("  Added shell_command.matter_restart_router_network")
    else:
        print("  shell_command already present")

    print("4. Reloading HA template and shell_command integrations...")
    call_service("template", "reload", {})
    call_service("shell_command", "reload", {})
    print("Done.")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(__file__))
    main()
