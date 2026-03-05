#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from ha_api import api


def get_states():
    try:
        return api("GET", "/api/states")
    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    states = get_states()
    print(f"{'Entity ID':<60} | {'State':<15} | {'Name'}")
    print("-" * 100)
    for s in states:
        eid = s['entity_id']
        name = s['attributes'].get('friendly_name', '')
        # 搜索关键词：lock, door, lumi
        if any(k in eid.lower() or k in name.lower() for k in ['lock', 'door', 'lumi']):
            print(f"{eid:<60} | {s['state']:<15} | {name}")
