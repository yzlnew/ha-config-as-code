#!/usr/bin/env python3
"""Check the feeder bowl with Codex CLI and publish the result to Home Assistant."""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import urllib3


CAMERA_ENTITY = "camera.192_168_50_237"
EVENT_TYPE = "pet_feeder_food_check_result"
MODEL = "gpt-5.6-luna"
TIMEZONE = ZoneInfo("Asia/Shanghai")
LOCK_PATH = Path("/tmp/pet_feeder_food_check.lock")
CODEX_TIMEOUT_SECONDS = 180

RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["low", "sufficient", "uncertain"],
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "food_coverage_percent": {
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
        },
        "summary": {"type": "string", "maxLength": 160},
    },
    "required": [
        "status",
        "confidence",
        "food_coverage_percent",
        "summary",
    ],
    "additionalProperties": False,
}

PROMPT = """只分析附带的喂食器截图，不要调用任何工具，也不要读取其他文件。

目标：判断喂食器前方外露的金属进食托盘里现在是否“快没猫粮了”。喂食器白色外壳固定盖住托盘后部是正常结构，不算遮挡；只评估画面中外露、供猫进食的金属区域。

判定标准：
- low：外露托盘清楚可见但几乎空了，只有零散少量颗粒、没有明显粮堆，约低于外露区域容量的 20%，应补充猫粮。
- sufficient：外露托盘清楚可见，并有一堆数量明显的猫粮，即使没有铺满整个托盘也不需要补充。
- uncertain：外露托盘本身被猫遮住、严重模糊、黑屏、过曝或裁出画面，无法可靠判断。

不要把猫、猫抓板、地板纹理或阴影当成猫粮。只有画面证据明确时才返回 low；不确定时返回 uncertain。summary 用简短中文说明可见状态。严格按给定 JSON Schema 返回。"""


class HomeAssistantClient:
    """Small HA client that verifies the token before doing any work."""

    def __init__(self) -> None:
        self.token = os.environ.get("HA_TOKEN", "")
        if not self.token:
            raise RuntimeError("HA_TOKEN is not configured")

        candidates = []
        for value in (
            os.environ.get("HA_URL"),
            os.environ.get("HA_EXTERNAL_URL"),
        ):
            if value and value.rstrip("/") not in candidates:
                candidates.append(value.rstrip("/"))
        if not candidates:
            raise RuntimeError("HA_URL or HA_EXTERNAL_URL is not configured")

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.base_url = self._verify(candidates[:2])

    def _verify(self, candidates: list[str]) -> str:
        errors = []
        for base_url in candidates:
            try:
                response = self.session.get(
                    f"{base_url}/api/", timeout=10, verify=False
                )
                if response.status_code == 200:
                    return base_url
                errors.append(f"{base_url}: HTTP {response.status_code}")
            except requests.RequestException as exc:
                errors.append(f"{base_url}: {exc}")
        raise RuntimeError("HA API verification failed: " + "; ".join(errors))

    def snapshot(self, destination: Path) -> None:
        response = self.session.get(
            f"{self.base_url}/api/camera_proxy/{CAMERA_ENTITY}",
            timeout=30,
            verify=False,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("image/") or len(response.content) < 1024:
            raise RuntimeError(
                f"Camera returned invalid content: {content_type}, "
                f"{len(response.content)} bytes"
            )
        destination.write_bytes(response.content)

    def publish_result(self, result: dict) -> None:
        response = self.session.post(
            f"{self.base_url}/api/events/{EVENT_TYPE}",
            json=result,
            timeout=15,
            verify=False,
        )
        response.raise_for_status()


def classify(snapshot_path: Path, workdir: Path) -> dict:
    codex_bin = os.environ.get("CODEX_BIN") or shutil.which("codex")
    if not codex_bin:
        raise RuntimeError("codex CLI is not available on PATH")

    schema_path = workdir / "result.schema.json"
    result_path = workdir / "result.json"
    schema_path.write_text(
        json.dumps(RESULT_SCHEMA, ensure_ascii=False), encoding="utf-8"
    )

    command = [
        codex_bin,
        "exec",
        "--ephemeral",
        "--ignore-rules",
        "--ignore-user-config",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--color",
        "never",
        "--model",
        MODEL,
        "--image",
        str(snapshot_path),
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(result_path),
        "--cd",
        str(workdir),
        PROMPT,
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=CODEX_TIMEOUT_SECONDS,
        check=False,
        env={**os.environ, "NO_COLOR": "1"},
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown error")[-2000:]
        raise RuntimeError(f"Codex exited with {completed.returncode}: {detail}")
    if not result_path.exists():
        raise RuntimeError("Codex did not write a structured result")

    result = json.loads(result_path.read_text(encoding="utf-8"))
    status = result.get("status")
    if status not in {"low", "sufficient", "uncertain"}:
        raise RuntimeError(f"Unexpected Codex status: {status!r}")
    confidence = float(result.get("confidence", 0))
    coverage = int(result.get("food_coverage_percent", 0))
    result["confidence"] = max(0.0, min(1.0, confidence))
    result["food_coverage_percent"] = max(0, min(100, coverage))
    result["summary"] = str(result.get("summary", ""))[:160]
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check feeder food level with Codex CLI"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify the current snapshot without publishing an HA event",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    with LOCK_PATH.open("w", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logging.info("Another feeder food check is already running; exiting")
            return 0

        ha = HomeAssistantClient()
        with tempfile.TemporaryDirectory(prefix="pet_feeder_food_check_") as temp:
            workdir = Path(temp)
            snapshot_path = workdir / "feeder.jpg"
            ha.snapshot(snapshot_path)
            try:
                result = classify(snapshot_path, workdir)
            except Exception as exc:
                logging.exception("Codex classification failed")
                result = {
                    "status": "uncertain",
                    "confidence": 0.0,
                    "food_coverage_percent": 0,
                    "summary": f"Codex 图像判断失败：{type(exc).__name__}",
                }

        result.update(
            {
                "checked_at": datetime.now(TIMEZONE).isoformat(timespec="seconds"),
                "camera_entity_id": CAMERA_ENTITY,
                "model": MODEL,
            }
        )
        logging.info("Feeder result: %s", json.dumps(result, ensure_ascii=False))
        if not args.dry_run:
            ha.publish_result(result)
            logging.info("Published %s to Home Assistant", EVENT_TYPE)
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        logging.exception("Feeder food check failed")
        raise SystemExit(1)
