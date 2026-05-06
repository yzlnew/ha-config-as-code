"""Deploy: SCP assets + (optionally) register Lovelace panel-iframe dashboard.

Run:
  cd /root/ha && .venv/bin/python scripts/the_daily/deploy.py            # full
  cd /root/ha && .venv/bin/python scripts/the_daily/deploy.py --data-only
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import sys as _sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
for _p in (_HERE, _SCRIPTS):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import _bootstrap  # noqa: F401
from _ws import WSClient

import ha_api  # type: ignore


ASSETS_DIR = Path("/root/ha/www/the-daily")
REMOTE_DIR = "/config/www/the-daily"
DASHBOARD_URL_PATH = "the-daily"


def _ssh_args() -> list[str]:
    user = os.environ["HA_SSH_USER"]
    host = os.environ["HA_SSH_HOST"]
    pw = os.environ["HA_SSH_PASSWORD"]
    return [
        "sshpass", "-p", pw,
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
        f"{user}@{host}",
    ]


def _scp(local: Path, remote: str) -> None:
    user = os.environ["HA_SSH_USER"]
    host = os.environ["HA_SSH_HOST"]
    pw = os.environ["HA_SSH_PASSWORD"]
    # -O forces legacy SCP protocol; HA SSH addon does not enable SFTP subsystem.
    cmd = [
        "sshpass", "-p", pw,
        "scp", "-O", "-q",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
        str(local),
        f"{user}@{host}:{remote}",
    ]
    subprocess.run(cmd, check=True)


def _ssh_exec(remote_cmd: str) -> tuple[int, str, str]:
    cmd = _ssh_args() + [remote_cmd]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def ensure_remote_dir() -> None:
    """Create /config/www/the-daily/ if missing. /config/www is root-owned, so we
    use passwordless sudo (hassio is in wheel group) to create + chown."""
    quoted = shlex.quote(REMOTE_DIR)
    user = os.environ["HA_SSH_USER"]
    cmd = (
        f"sudo -n mkdir -p {quoted} && "
        f"sudo -n chown {user}:{user} {quoted} && echo OK"
    )
    rc, out, err = _ssh_exec(cmd)
    if rc != 0 or "OK" not in out:
        raise RuntimeError(f"mkdir failed: rc={rc} stdout={out!r} stderr={err!r}")


def push_data_only() -> None:
    data = ASSETS_DIR / "data.json"
    if not data.exists():
        raise FileNotFoundError(f"{data} does not exist — run compose.py first")
    _scp(data, f"{REMOTE_DIR}/data.json")
    print(f"[deploy] data.json → {REMOTE_DIR}/")


def push_full() -> None:
    files = ["index.html", "style.css", "app.js", "data.json"]
    missing = [f for f in files if not (ASSETS_DIR / f).exists()]
    if missing:
        raise FileNotFoundError(f"missing assets: {missing} — run compose.py first")
    ensure_remote_dir()
    for f in files:
        _scp(ASSETS_DIR / f, f"{REMOTE_DIR}/{f}")
    print(f"[deploy] uploaded {len(files)} files to {REMOTE_DIR}/")


# ---- Lovelace dashboard registration ------------------------------------

DASHBOARD_CONFIG = {
    "title": "The Daily",
    "views": [
        {
            "title": "The Daily",
            "path": "main",
            "panel": True,
            "cards": [
                {
                    "type": "iframe",
                    "url": "/local/the-daily/index.html",
                    "aspect_ratio": "100%",
                }
            ],
        }
    ],
}


def register_dashboard() -> None:
    with WSClient() as ws:
        # 1. List dashboards
        existing = ws.request({"type": "lovelace/dashboards/list"})
        dashboards = existing.get("result") or []
        match = next((d for d in dashboards if d.get("url_path") == DASHBOARD_URL_PATH), None)

        if not match:
            create = ws.request({
                "type": "lovelace/dashboards/create",
                "url_path": DASHBOARD_URL_PATH,
                "title": "The Daily",
                "icon": "mdi:newspaper-variant",
                "show_in_sidebar": True,
                "require_admin": False,
                "mode": "storage",
            })
            if not create.get("success"):
                raise RuntimeError(f"create dashboard failed: {create.get('error')}")
            print(f"[deploy] dashboard created (sidebar: 'The Daily')")
        else:
            print(f"[deploy] dashboard already exists, updating config")

        # 2. Save lovelace config under that dashboard url_path
        save = ws.request({
            "type": "lovelace/config/save",
            "url_path": DASHBOARD_URL_PATH,
            "config": DASHBOARD_CONFIG,
        })
        if not save.get("success"):
            raise RuntimeError(f"save config failed: {save.get('error')}")
        print(f"[deploy] dashboard config saved")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy The Daily to HA")
    parser.add_argument("--data-only", action="store_true", help="only push data.json")
    parser.add_argument("--skip-dashboard", action="store_true", help="don't register Lovelace dashboard")
    args = parser.parse_args()

    for var in ("HA_SSH_HOST", "HA_SSH_USER", "HA_SSH_PASSWORD"):
        if not os.environ.get(var):
            print(f"ERROR: {var} not set", file=sys.stderr)
            return 1

    try:
        if args.data_only:
            push_data_only()
        else:
            push_full()
            if not args.skip_dashboard:
                register_dashboard()
    except subprocess.CalledProcessError as exc:
        print(f"[deploy] subprocess failed: rc={exc.returncode}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[deploy] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
