#!/usr/bin/env python3
"""Push the rendered e-ink PNG to HA's /config/www/eink/dashboard.png.

The ESPHome panel then downloads it from http://<HA>:8123/local/eink/dashboard.png.

Transport: uses the `sshpass` binary when present (the always-on box that runs
the_daily cron has it); otherwise falls back to pure-python paramiko, so this
also runs from a dev machine. /config/www is root-owned, so the dir is created
with passwordless sudo (hassio is in the wheel group); the HA SSH add-on has no
SFTP subsystem, so files are streamed over an exec channel / legacy scp.

Run:
  set -a && source .env && set +a
  .venv/bin/python scripts/eink/render.py && .venv/bin/python scripts/eink/deploy.py
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCAL_PNG = HERE / "out" / "dashboard.png"
REMOTE_DIR = "/config/www/eink"
REMOTE_PNG = f"{REMOTE_DIR}/dashboard.png"


def _env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        print(f"[deploy] missing env {name}; run: set -a && source .env && set +a", file=sys.stderr)
        raise SystemExit(2)
    return v


# ── sshpass transport ────────────────────────────────────────────────────────
def _sshpass_run(cmd: str) -> tuple[int, str, str]:
    base = [
        "sshpass", "-p", _env("HA_SSH_PASSWORD"),
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR",
        f"{_env('HA_SSH_USER')}@{_env('HA_SSH_HOST')}", cmd,
    ]
    r = subprocess.run(base, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _sshpass_put(local: Path, remote: str) -> None:
    cmd = [
        "sshpass", "-p", _env("HA_SSH_PASSWORD"),
        "scp", "-O", "-q", "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR",
        str(local), f"{_env('HA_SSH_USER')}@{_env('HA_SSH_HOST')}:{remote}",
    ]
    subprocess.run(cmd, check=True)


# ── paramiko transport ───────────────────────────────────────────────────────
def _paramiko_client():
    import paramiko  # type: ignore

    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(
        _env("HA_SSH_HOST"), username=_env("HA_SSH_USER"),
        password=_env("HA_SSH_PASSWORD"), timeout=12, allow_agent=False, look_for_keys=False,
    )
    return cli


def _paramiko_run(cli, cmd: str) -> tuple[int, str, str]:
    _in, out, err = cli.exec_command(cmd, timeout=20)
    rc = out.channel.recv_exit_status()
    return rc, out.read().decode(errors="replace"), err.read().decode(errors="replace")


def _paramiko_put(cli, local: Path, remote: str) -> None:
    # No SFTP subsystem on the HA SSH add-on; stream bytes through `cat > file`.
    data = local.read_bytes()
    chan = cli.get_transport().open_session()
    chan.exec_command(f"cat > {shlex.quote(remote)}")
    chan.sendall(data)
    chan.shutdown_write()
    rc = chan.recv_exit_status()
    if rc != 0:
        raise RuntimeError(f"upload failed rc={rc}: {chan.recv_stderr(4096).decode(errors='replace')}")


# ── deploy ───────────────────────────────────────────────────────────────────
def main() -> int:
    if not LOCAL_PNG.exists():
        print(f"[deploy] {LOCAL_PNG} missing — run render.py first", file=sys.stderr)
        return 2

    mkdir = (
        f"sudo -n mkdir -p {shlex.quote(REMOTE_DIR)} && "
        f"sudo -n chown {_env('HA_SSH_USER')}:{_env('HA_SSH_USER')} {shlex.quote(REMOTE_DIR)} && echo OK"
    )

    use_sshpass = shutil.which("sshpass") is not None
    if use_sshpass:
        rc, out, err = _sshpass_run(mkdir)
        if rc != 0 or "OK" not in out:
            raise RuntimeError(f"mkdir failed: rc={rc} out={out!r} err={err!r}")
        _sshpass_put(LOCAL_PNG, REMOTE_PNG)
    else:
        cli = _paramiko_client()
        try:
            rc, out, err = _paramiko_run(cli, mkdir)
            if rc != 0 or "OK" not in out:
                raise RuntimeError(f"mkdir failed: rc={rc} out={out!r} err={err!r}")
            _paramiko_put(cli, LOCAL_PNG, REMOTE_PNG)
        finally:
            cli.close()

    print(f"[deploy] {LOCAL_PNG.name} ({LOCAL_PNG.stat().st_size}B) → {REMOTE_PNG}"
          f"  via {'sshpass' if use_sshpass else 'paramiko'}")
    print(f"[deploy] panel URL: http://{os.environ['HA_SSH_HOST']}:8123/local/eink/dashboard.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
