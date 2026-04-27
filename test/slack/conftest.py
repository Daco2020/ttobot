"""슬랙 이벤트 핸들러 테스트 공통 픽스처.

핸들러 함수들은 슬랙-볼트가 ack/body/say/client/user/service/point_service를 인자로 넘겨주는데,
테스트에서는 이 인자들을 직접 만들어 함수를 호출한다. 여기서는 그 인자들을 만드는 헬퍼를 제공한다.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def ack() -> AsyncMock:
    """slack-bolt의 ack/say는 비동기 호출 가능 객체."""
    return AsyncMock()


@pytest.fixture
def say() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def slack_service() -> AsyncMock:
    """SlackService를 spec 없이 mock으로 대체. 메서드 호출은 자동으로 MagicMock이 된다."""
    return AsyncMock()


@pytest.fixture
def point_service_mock() -> AsyncMock:
    return AsyncMock()


# ---------------------------------------------------------------------------
# Body 빌더
# ---------------------------------------------------------------------------


def make_command_body(
    *,
    user_id: str = "U_TEST",
    channel_id: str = "C_TEST",
    command: str = "/제출",
    text: str = "",
    trigger_id: str = "trigger.123",
    response_url: str = "https://hooks.slack.example/test",
    **extra: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "token": "verification",
        "team_id": "T_TEST",
        "team_domain": "team",
        "channel_id": channel_id,
        "channel_name": "channel",
        "user_id": user_id,
        "user_name": "tester",
        "command": command,
        "text": text,
        "api_app_id": "A_TEST",
        "is_enterprise_install": "false",
        "response_url": response_url,
        "trigger_id": trigger_id,
    }
    body.update(extra)
    return body


def make_action_body(
    *,
    action_id: str = "do_something",
    user_id: str = "U_TEST",
    trigger_id: str = "trigger.123",
    response_url: str = "https://hooks.slack.example/test",
    actions: list[dict[str, Any]] | None = None,
    view: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    channel_id: str = "C_TEST",
    **extra: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": "block_actions",
        "user": {"id": user_id, "username": "tester", "name": "tester", "team_id": "T_TEST"},
        "api_app_id": "A_TEST",
        "token": "verification",
        "container": {
            "type": "view",
            "view_id": "V_TEST",
            "message_ts": "0",
            "channel_id": channel_id,
            "is_ephemeral": False,
        },
        "trigger_id": trigger_id,
        "team": {"id": "T_TEST", "domain": "team"},
        "enterprise": "",
        "is_enterprise_install": False,
        "channel": {"id": channel_id, "name": "channel"},
        "state": state or {"values": {}},
        "response_url": response_url,
        "view": view or {},
        "actions": actions
        or [
            {
                "action_id": action_id,
                "block_id": "block",
                "text": {"type": "plain_text", "text": "버튼"},
                "value": "",
                "type": "button",
                "action_ts": "0",
            }
        ],
    }
    body.update(extra)
    return body


def make_view_body(
    *,
    user_id: str = "U_TEST",
    callback_id: str = "submit_view",
    private_metadata: str = "",
    state_values: dict[str, Any] | None = None,
    view_id: str = "V_TEST",
    **extra: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": "view_submission",
        "team": {"id": "T_TEST", "domain": "team"},
        "user": {"id": user_id, "username": "tester", "name": "tester", "team_id": "T_TEST"},
        "api_app_id": "A_TEST",
        "token": "verification",
        "trigger_id": "trigger.123",
        "view": {
            "id": view_id,
            "team_id": "T_TEST",
            "type": "modal",
            "blocks": [],
            "private_metadata": private_metadata,
            "callback_id": callback_id,
            "state": {"values": state_values or {}},
            "hash": "",
            "title": {"type": "plain_text", "text": "제목"},
            "clear_on_close": False,
            "notify_on_close": False,
            "close": "",
            "submit": {"type": "plain_text", "text": "제출"},
            "previous_view_id": "",
            "root_view_id": view_id,
            "app_id": "A_TEST",
            "external_id": "",
            "app_installed_team_id": "T_TEST",
            "bot_id": "B_TEST",
        },
        "response_urls": [],
        "is_enterprise_install": False,
        "enterprise": "",
    }
    body.update(extra)
    return body


def make_message_body(
    *,
    user_id: str = "U_TEST",
    channel_id: str = "C_TEST",
    text: str = "안녕",
    ts: str = "1735700000.000000",
    thread_ts: str | None = None,
    subtype: str | None = None,
    files: list[dict[str, Any]] | None = None,
    message_changed_user: str | None = None,
) -> dict[str, Any]:
    if subtype == "message_changed":
        event: dict[str, Any] = {
            "type": "message",
            "subtype": "message_changed",
            "channel": channel_id,
            "message": {
                "user": message_changed_user or user_id,
                "type": "message",
                "ts": ts,
                "client_msg_id": "msg",
                "text": text,
                "team": "T_TEST",
                "blocks": [],
                "thread_ts": thread_ts,
                "reply_users": [],
            },
            "previous_message": {},
            "hidden": False,
            "ts": ts,
            "event_ts": ts,
            "channel_type": "channel",
        }
    else:
        event = {
            "user": user_id,
            "type": "message",
            "ts": ts,
            "client_msg_id": "msg",
            "text": text,
            "team": "T_TEST",
            "blocks": [],
            "channel": channel_id,
            "event_ts": ts,
            "channel_type": "channel",
            "thread_ts": thread_ts,
        }
        if subtype:
            event["subtype"] = subtype
        if files is not None:
            event["files"] = files
    return {
        "token": "verification",
        "team_id": "T_TEST",
        "context_team_id": "T_TEST",
        "context_enterprise_id": None,
        "api_app_id": "A_TEST",
        "event": event,
        "type": "event_callback",
        "event_id": "Ev_TEST",
        "event_time": 1735700000,
        "authorizations": [],
        "is_ext_shared_channel": False,
        "event_context": "ctx",
    }


def make_reaction_body(
    *,
    user_id: str = "U_TEST",
    item_user: str = "U_OTHER",
    channel_id: str = "C_TEST",
    item_ts: str = "1735700000.000000",
    reaction: str = "thumbsup",
    event_ts: str = "1735700000.100000",
) -> dict[str, Any]:
    return {
        "token": "verification",
        "team_id": "T_TEST",
        "context_team_id": "T_TEST",
        "context_enterprise_id": None,
        "api_app_id": "A_TEST",
        "event": {
            "user": user_id,
            "type": "reaction_added",
            "reaction": reaction,
            "item": {"type": "message", "channel": channel_id, "ts": item_ts},
            "item_user": item_user,
            "event_ts": event_ts,
        },
        "type": "event_callback",
        "event_id": "Ev_TEST",
        "event_time": 1735700000,
        "authorizations": [],
        "is_ext_shared_channel": False,
        "event_context": "ctx",
    }


@pytest.fixture
def slack_bodies():
    """body 빌더들을 한 번에 노출."""
    return type(
        "SlackBodies",
        (),
        {
            "command": staticmethod(make_command_body),
            "action": staticmethod(make_action_body),
            "view": staticmethod(make_view_body),
            "message": staticmethod(make_message_body),
            "reaction": staticmethod(make_reaction_body),
        },
    )
