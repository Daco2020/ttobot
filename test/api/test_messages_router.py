"""GET / POST /v1/messages — 슬랙 메시지 조회/수정 라우터 테스트.

핵심 외부 의존성: `app.api.views.contents.slack_app.client`
이 객체는 `app.slack.event_handler.app.client` 와 동일한 싱글톤이다.
테스트에서는 `mocker.patch.object(slack_app.client, "메서드명", ...)` 형태로 메서드만 갈아끼운다.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from slack_sdk.errors import SlackApiError

from app.api.views import contents as contents_view
from app.config import settings


@pytest.fixture
def slack_client(mocker: MockerFixture):
    """slack_app.client 의 호출 메서드들을 기본적으로 mock 으로 대체."""
    client = contents_view.slack_app.client
    mocker.patch.object(client, "conversations_history")
    mocker.patch.object(client, "conversations_replies")
    mocker.patch.object(client, "chat_update")
    mocker.patch.object(client, "chat_getPermalink")
    return client


def _admin_user(factory):
    return factory.make_user(user_id=settings.ADMIN_IDS[0], name="관리자")


def _non_admin_user(factory):
    return factory.make_user(user_id="U_GUEST", name="일반유저")


# ---------------------------------------------------------------------------
# GET /v1/messages
# ---------------------------------------------------------------------------


def test_get_message_admin_returns_single_message(
    client: TestClient, auth_for, factory, slack_client
) -> None:
    """✅ admin 호출 → conversations_history → 단일 메시지 dict 반환."""
    # given
    auth_for(_admin_user(factory))
    target_ts = "1700000000.000100"
    slack_client.conversations_history.return_value = {
        "messages": [
            {
                "ts": target_ts,
                "text": "원본 메시지",
                "blocks": [{"type": "section"}],
                "attachments": [{"id": 1}],
            }
        ]
    }

    # when
    response = client.get(
        "/v1/messages",
        params={"ts": target_ts, "channel_id": "C_TEST"},
    )

    # then
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "원본 메시지"
    assert body["blocks"] == [{"type": "section"}]
    assert body["attachments"] == [{"id": 1}]
    slack_client.conversations_history.assert_awaited_once()
    kwargs = slack_client.conversations_history.await_args.kwargs
    assert kwargs["channel"] == "C_TEST"
    assert kwargs["latest"] == target_ts
    assert kwargs["limit"] == 1


def test_get_message_admin_multiple_messages_returns_list(
    client: TestClient, auth_for, factory, slack_client
) -> None:
    """✅ multiple_messages=True → 리스트로 응답."""
    auth_for(_admin_user(factory))
    slack_client.conversations_history.return_value = {
        "messages": [
            {"ts": "1.0", "text": "a", "blocks": [], "attachments": []},
            {"ts": "2.0", "text": "b", "blocks": []},  # attachments 없는 케이스
        ]
    }

    response = client.get(
        "/v1/messages",
        params={"ts": "1.0", "channel_id": "C_TEST", "multiple_messages": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 2
    assert body[0]["text"] == "a"
    assert body[1]["attachments"] == []
    slack_client.conversations_history.await_args.kwargs["limit"] == 10


def test_get_message_type_reply_uses_conversations_replies(
    client: TestClient, auth_for, factory, slack_client
) -> None:
    """✅ type=reply → conversations_replies 호출."""
    auth_for(_admin_user(factory))
    target_ts = "1.0"
    slack_client.conversations_replies.return_value = {
        "messages": [
            {"ts": target_ts, "text": "스레드", "blocks": [], "attachments": []}
        ]
    }

    response = client.get(
        "/v1/messages",
        params={"ts": target_ts, "channel_id": "C_TEST", "type": "reply"},
    )

    assert response.status_code == 200
    assert response.json()["text"] == "스레드"
    slack_client.conversations_replies.assert_awaited_once()
    slack_client.conversations_history.assert_not_called()


def test_get_message_non_admin_returns_403(
    client: TestClient, auth_for, factory, slack_client
) -> None:
    """⚠️ admin 이 아닌 유저 → 403."""
    auth_for(_non_admin_user(factory))

    response = client.get(
        "/v1/messages", params={"ts": "1.0", "channel_id": "C_TEST"}
    )

    assert response.status_code == 403
    assert "수정 권한이 없습니다" in response.json()["detail"]
    slack_client.conversations_history.assert_not_called()


def test_get_message_without_token_returns_403(
    client: TestClient, slack_client
) -> None:
    """🌀 인증 누락 → 403 (current_user 단에서 차단)."""
    response = client.get(
        "/v1/messages", params={"ts": "1.0", "channel_id": "C_TEST"}
    )
    assert response.status_code == 403
    slack_client.conversations_history.assert_not_called()


def test_get_message_when_target_ts_not_found_returns_404(
    client: TestClient, auth_for, factory, slack_client
) -> None:
    """⚠️ ts 매칭이 안 되면 → 404."""
    auth_for(_admin_user(factory))
    slack_client.conversations_history.return_value = {
        "messages": [{"ts": "다른ts", "text": "x", "blocks": []}]
    }

    response = client.get(
        "/v1/messages", params={"ts": "찾는ts", "channel_id": "C_TEST"}
    )

    assert response.status_code == 404
    assert "콘텐츠를 찾을 수 없습니다" in response.json()["detail"]


def test_get_message_when_slack_api_error_returns_409(
    client: TestClient, auth_for, factory, slack_client
) -> None:
    """⚠️ Slack API 호출이 실패하면 → 409."""
    auth_for(_admin_user(factory))
    slack_client.conversations_history.side_effect = SlackApiError(
        message="boom", response={"error": "channel_not_found"}
    )

    response = client.get(
        "/v1/messages", params={"ts": "1.0", "channel_id": "C_TEST"}
    )

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# POST /v1/messages
# ---------------------------------------------------------------------------


def _update_payload(**overrides: Any) -> dict[str, Any]:
    base = {
        "text": "수정된 메시지",
        "blocks": [{"type": "section"}],
        "attachments": [{"id": 1}],
    }
    base.update(overrides)
    return base


def test_post_message_admin_updates_and_returns_permalink(
    client: TestClient, auth_for, factory, slack_client
) -> None:
    """✅ admin → chat_update + permalink 응답."""
    auth_for(_admin_user(factory))
    slack_client.chat_getPermalink.return_value = {
        "permalink": "https://slack.example/permalink"
    }

    response = client.post(
        "/v1/messages",
        params={"ts": "1.0", "channel_id": "C_TEST"},
        json=_update_payload(),
    )

    assert response.status_code == 200
    assert response.json() == {"permalink": "https://slack.example/permalink"}

    slack_client.chat_update.assert_awaited_once()
    kwargs = slack_client.chat_update.await_args.kwargs
    assert kwargs["channel"] == "C_TEST"
    assert kwargs["ts"] == "1.0"
    assert kwargs["text"] == "수정된 메시지"
    slack_client.chat_getPermalink.assert_awaited_once()


def test_post_message_non_admin_returns_403(
    client: TestClient, auth_for, factory, slack_client
) -> None:
    """⚠️ admin 이 아닌 유저 → 403."""
    auth_for(_non_admin_user(factory))

    response = client.post(
        "/v1/messages",
        params={"ts": "1.0", "channel_id": "C_TEST"},
        json=_update_payload(),
    )

    assert response.status_code == 403
    slack_client.chat_update.assert_not_called()


def test_post_message_when_slack_api_error_returns_409(
    client: TestClient, auth_for, factory, slack_client
) -> None:
    """⚠️ chat_update 가 SlackApiError 를 던지면 → 409."""
    auth_for(_admin_user(factory))
    slack_client.chat_update.side_effect = SlackApiError(
        message="boom", response={"error": "message_not_found"}
    )

    response = client.post(
        "/v1/messages",
        params={"ts": "1.0", "channel_id": "C_TEST"},
        json=_update_payload(),
    )

    assert response.status_code == 409
