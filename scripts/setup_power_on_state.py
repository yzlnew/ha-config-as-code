#!/usr/bin/env python3
"""Set all lights to power-on = memory/previous (not 'turn on').

Ensures lights don't all blast on after a power outage.
Idempotent — safe to re-run anytime, especially after adding new devices.

Three groups with different option values:
  - Xiaomi Mesh lights: "断电记忆"
  - Xiaomi 浴霸: "记忆"
  - Matter lights: "previous"
"""

import time
from ha_api import api, call_service


def find_power_on_entities():
    """Auto-discover all power-on state select entities and their target values."""
    states = api("GET", "/api/states")
    entities = []

    for s in states:
        eid = s["entity_id"]
        if not eid.startswith("select."):
            continue

        options = s["attributes"].get("options", [])
        state = s["state"]
        name = s["attributes"].get("friendly_name", "")

        # Match known power-on entity patterns
        is_power_on = (
            "default_power_on_state" in eid
            or "qi_dong_shi_de_kai_ji_xing_wei" in eid
            or eid == "select.trytogo_power_on_behavior"
        )
        if not is_power_on:
            continue

        # Determine target value based on available options
        if "previous" in options:
            target = "previous"
        elif "断电记忆" in options:
            target = "断电记忆"
        elif "记忆" in options:
            target = "记忆"
        else:
            continue

        entities.append({
            "entity_id": eid,
            "name": name,
            "current": state,
            "target": target,
        })

    return entities


def main():
    print("Discovering power-on state entities...")
    entities = find_power_on_entities()
    print(f"Found {len(entities)} entities\n")

    already_ok = 0
    changed = 0
    failed = 0

    for e in sorted(entities, key=lambda x: x["entity_id"]):
        eid = e["entity_id"]
        if e["current"] == e["target"]:
            print(f"  [OK] {e['name']} ({eid}) = {e['current']}")
            already_ok += 1
            continue

        try:
            call_service("select", "select_option", {
                "entity_id": eid,
                "option": e["target"],
            })
            print(f"  [SET] {e['name']} ({eid}): {e['current']} -> {e['target']}")
            changed += 1
        except Exception as ex:
            print(f"  [FAIL] {e['name']} ({eid}): {ex}")
            failed += 1
        time.sleep(0.3)

    print(f"\nDone: {already_ok} already OK, {changed} changed, {failed} failed")


if __name__ == "__main__":
    main()
