#!/usr/bin/env python3
"""Create the HA automation that handles feeder vision results and actions."""

from __future__ import annotations

import json
import ssl
import time

import websocket

from ha_api import HA_URL, TOKEN, api, call_service, put_automation


AUTOMATION_ID = "pet_feeder_food_ai_check"
AUTOMATION_ENTITY_ID = f"automation.{AUTOMATION_ID}"
AUTOMATION_NAME = "宠物喂食：AI余粮检查与补粮"
AUTOMATION_ICON = "mdi:bowl-mix"
CAMERA_ENTITY = "camera.192_168_50_237"
IPHONE_NOTIFY_SERVICE = "notify.mobile_app_robins_iphone"
FEEDER_ACTION_ENTITY = "notify.mmgg_cn_467135245_inland_pet_food_out_a_2_1"
MANUAL_ACTION = "PET_FEEDER_ADD_5_PORTIONS"


def camera_notification_data(action_title: str) -> dict:
    return {
        "entity_id": CAMERA_ENTITY,
        "tag": "pet_feeder_food_check",
        "actions": [
            {"action": MANUAL_ACTION, "title": action_title},
            {
                "action": "URI",
                "title": "查看摄像头",
                "uri": f"entityId:{CAMERA_ENTITY}",
            },
        ],
    }


def notify_action(title: str, message: str, action_title: str) -> dict:
    return {
        "action": IPHONE_NOTIFY_SERVICE,
        "data": {
            "title": title,
            "message": message,
            "data": camera_notification_data(action_title),
        },
    }


def feed_five_action() -> dict:
    return {
        "action": "notify.send_message",
        "target": {"entity_id": FEEDER_ACTION_ENTITY},
        "data": {"message": "5"},
    }


AUTOMATION_CONFIG = {
    "alias": AUTOMATION_NAME,
    "description": (
        "接收本机 Codex CLI 的喂食器截图判断；低余粮时自动加 5 份并发送"
        "带摄像头预览和手动加粮按钮的手机通知。"
    ),
    "trigger": [
        {
            "platform": "event",
            "event_type": "pet_feeder_food_check_result",
            "id": "food_check",
        },
        {
            "platform": "event",
            "event_type": "mobile_app_notification_action",
            "event_data": {"action": MANUAL_ACTION},
            "id": "manual_add",
        },
    ],
    "condition": [],
    "action": [
        {
            "choose": [
                {
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": "{{ trigger.id == 'manual_add' }}",
                        }
                    ],
                    "sequence": [
                        feed_five_action(),
                        notify_action(
                            "喂食器：已手动加粮",
                            "已通过通知按钮添加 5 份猫粮。",
                            "再加 5 份",
                        ),
                    ],
                },
                {
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": (
                                "{{ trigger.id == 'food_check' and "
                                "trigger.event.data.status == 'low' and "
                                "(trigger.event.data.confidence | float(0)) >= 0.8 }}"
                            ),
                        }
                    ],
                    "sequence": [
                        feed_five_action(),
                        notify_action(
                            "喂食器：猫粮快没了",
                            (
                                "视觉状态：快没了（托盘约 "
                                "{{ trigger.event.data.food_coverage_percent | int(0) }}%，"
                                "置信度 {{ ((trigger.event.data.confidence | float(0)) * 100) "
                                "| round(0) | int }}%）。已自动添加 5 份。"
                                "{{ trigger.event.data.summary }}"
                            ),
                            "再加 5 份",
                        ),
                    ],
                },
                {
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": (
                                "{{ trigger.id == 'food_check' and "
                                "trigger.event.data.status in ['low', 'uncertain'] }}"
                            ),
                        }
                    ],
                    "sequence": [
                        notify_action(
                            "喂食器：请确认余粮",
                            (
                                "视觉状态：无法可靠确认，未自动出粮。"
                                "{{ trigger.event.data.summary }}"
                            ),
                            "添加 5 份",
                        )
                    ],
                },
            ]
        }
    ],
    "mode": "queued",
    "max": 5,
}


def ws_call(ws, message_id: int, payload: dict) -> dict:
    payload = {"id": message_id, **payload}
    ws.send(json.dumps(payload))
    response = json.loads(ws.recv())
    if not response.get("success"):
        raise RuntimeError(f"WebSocket call failed: {response.get('error')}")
    return response


def configure_registry() -> None:
    ws_url = HA_URL.replace("https://", "wss://").replace("http://", "ws://")
    ws = websocket.create_connection(
        f"{ws_url}/api/websocket",
        timeout=20,
        sslopt={"cert_reqs": ssl.CERT_NONE},
    )
    try:
        ws.recv()
        ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        auth = json.loads(ws.recv())
        if auth.get("type") != "auth_ok":
            raise RuntimeError(f"WebSocket auth failed: {auth}")

        entities = ws_call(
            ws, 1, {"type": "config/entity_registry/list"}
        )["result"]
        entity = next(
            (
                item
                for item in entities
                if item.get("unique_id") == AUTOMATION_ID
                or item.get("entity_id") == AUTOMATION_ENTITY_ID
            ),
            None,
        )
        if not entity:
            raise RuntimeError("Could not find the feeder automation entity")

        update = {
            "type": "config/entity_registry/update",
            "entity_id": entity["entity_id"],
            "name": AUTOMATION_NAME,
            "icon": AUTOMATION_ICON,
        }
        if entity["entity_id"] != AUTOMATION_ENTITY_ID:
            update["new_entity_id"] = AUTOMATION_ENTITY_ID
        ws_call(ws, 2, update)
        print(f"  [OK] registry: {AUTOMATION_ENTITY_ID} ({AUTOMATION_ICON})")
    finally:
        ws.close()


def main() -> None:
    # Required token test before configuration writes.
    result = api("GET", "/api/")
    if result.get("message") != "API running.":
        raise RuntimeError(f"Unexpected HA API response: {result}")
    print("  [OK] HA API token verified")

    if not put_automation(AUTOMATION_ID, AUTOMATION_CONFIG):
        raise RuntimeError("Failed to create feeder automation")
    call_service("automation", "reload")
    time.sleep(2)
    configure_registry()


if __name__ == "__main__":
    main()
