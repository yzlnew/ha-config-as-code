"""Shared Home Assistant API client with connection reuse."""

import json
import os
import sys
import requests
import urllib3

# Load .env file if python-dotenv is available, otherwise rely on os.getenv
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

# Suppress InsecureRequestWarning for verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HA_URL = os.getenv("HA_EXTERNAL_URL") or os.getenv("HA_URL")
TOKEN = os.getenv("HA_TOKEN")

if not HA_URL or not TOKEN:
    print("ERROR: HA_URL/HA_EXTERNAL_URL and HA_TOKEN must be set in .env or environment.", file=sys.stderr)
    sys.exit(1)

_session = None


def session():
    """Get or create a reusable requests.Session with HA auth."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        })
        _session.verify = False
        _session.timeout = 30
    return _session


def api(method, path, data=None):
    resp = session().request(method, f"{HA_URL}{path}", json=data, timeout=30)
    resp.raise_for_status()
    return resp.json()


def call_service(domain, service, data=None):
    return api("POST", f"/api/services/{domain}/{service}", data)


def put_automation(automation_id, config):
    try:
        result = api("POST", f"/api/config/automation/config/{automation_id}", config)
        print(f"  [OK] {automation_id}")
        return True
    except Exception as e:
        print(f"  [FAIL] {automation_id} -> {e}")
        return False


def delete_automation(automation_id):
    try:
        result = api("DELETE", f"/api/config/automation/config/{automation_id}")
        print(f"  [DEL] {automation_id}")
        return True
    except Exception as e:
        print(f"  [SKIP] {automation_id} -> {e}")
        return False


def put_scene(scene_id, config):
    try:
        result = api("POST", f"/api/config/scene/config/{scene_id}", config)
        print(f"  [OK] scene.{scene_id}")
        return True
    except Exception as e:
        print(f"  [FAIL] scene.{scene_id} -> {e}")
        return False
