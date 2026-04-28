"""슬랙 subscriptions 이벤트 핸들러 테스트.

대상: app/slack/events/subscriptions.py
- open_subscribe_member_view
- subscribe_member
- unsubscribe_member
- open_subscription_permalink
- _process_user_subscription (검증 5단계)
- _get_subscribe_member_view (구독 0/N 명에 따른 블록)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.constants import BOT_IDS
from app.slack.events import subscriptions as sub_events
from test import factories
from test.slack.conftest import make_action_body


# ---------------------------------------------------------------------------
# _process_user_subscription — 검증 5단계
#
# NOTE: 라우터 코드에서 각 분기는 elif 가 아닌 if 로 작성되어 있어,
#       마지막으로 매칭된 분기의 메시지가 최종 결과가 된다. 또한 service.get_only_user()는
#       BotException 을 던질 수 있는 메서드이지만, 내부 분기에서는 None 반환 케이스도 처리한다.
# ---------------------------------------------------------------------------


def _make_service_with_no_subscriptions():
    """기본 mock 서비스 — 구독 0건, target_user 정상 반환."""
    service = MagicMock()
    service.fetch_subscriptions_by_user_id.return_value = []
    service.get_only_user.return_value = factories.make_user(
        user_id="U_TARGET", name="대상유저"
    )
    return service


def test_process_self_subscription_blocked() -> None:
    """⚠️ 자기 자신 구독 시도 → '자기 자신은 구독할 수 없어요.'"""
    user = factories.make_user(user_id="U_X")
    service = _make_service_with_no_subscriptions()

    msg = sub_events._process_user_subscription(user, service, "U_X")

    assert "자기 자신은 구독할 수 없어요" in msg
    service.create_subscription.assert_not_called()


def test_process_bot_subscription_blocked() -> None:
    """⚠️ 봇 구독 시도 → '봇은 구독할 수 없어요.'"""
    user = factories.make_user(user_id="U_X")
    service = _make_service_with_no_subscriptions()

    msg = sub_events._process_user_subscription(user, service, BOT_IDS[0])

    assert "봇은 구독할 수 없어요" in msg
    service.create_subscription.assert_not_called()


def test_process_too_many_subscriptions_blocked() -> None:
    """⚠️ 이미 5명 구독 → '구독은 최대 5명까지 가능해요.'"""
    user = factories.make_user(user_id="U_X")
    service = MagicMock()
    service.fetch_subscriptions_by_user_id.return_value = [
        factories.make_subscription(target_user_id=f"U_S_{i}") for i in range(5)
    ]
    service.get_only_user.return_value = factories.make_user(user_id="U_TARGET")

    msg = sub_events._process_user_subscription(user, service, "U_TARGET")

    assert "최대 5명까지" in msg
    service.create_subscription.assert_not_called()


def test_process_target_user_missing_blocked() -> None:
    """⚠️ 대상 유저 못 찾음 → '구독할 멤버를 찾을 수 없습니다.'"""
    user = factories.make_user(user_id="U_X")
    service = MagicMock()
    service.fetch_subscriptions_by_user_id.return_value = []
    service.get_only_user.return_value = None  # 미존재

    msg = sub_events._process_user_subscription(user, service, "U_GHOST")

    assert "찾을 수 없습니다" in msg
    service.create_subscription.assert_not_called()


def test_process_already_subscribed_blocked() -> None:
    """⚠️ 이미 구독 중인 멤버 → '이미 구독한 멤버입니다.'"""
    user = factories.make_user(user_id="U_X")
    service = MagicMock()
    service.fetch_subscriptions_by_user_id.return_value = [
        factories.make_subscription(target_user_id="U_TARGET")
    ]
    service.get_only_user.return_value = factories.make_user(user_id="U_TARGET")

    msg = sub_events._process_user_subscription(user, service, "U_TARGET")

    assert "이미 구독한 멤버" in msg
    service.create_subscription.assert_not_called()


def test_process_valid_subscription_creates() -> None:
    """✅ 모든 검증 통과 → service.create_subscription + 빈 문자열 반환."""
    user = factories.make_user(user_id="U_X")
    service = _make_service_with_no_subscriptions()
    service.get_only_user.return_value = factories.make_user(
        user_id="U_TARGET", channel_id="C_TARGET"
    )

    msg = sub_events._process_user_subscription(user, service, "U_TARGET")

    assert msg == ""
    service.create_subscription.assert_called_once_with(
        user_id="U_X",
        target_user_id="U_TARGET",
        target_user_channel="C_TARGET",
    )


# ---------------------------------------------------------------------------
# open_subscribe_member_view
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_subscribe_member_view_no_value_opens_blank_modal(
    ack, fake_slack_client, factory
) -> None:
    """✅ action value 없음 → 빈 메시지 + 모달 open."""
    user = factory.make_user(user_id="U_X")
    service = _make_service_with_no_subscriptions()

    body = make_action_body(
        actions=[
            {
                "action_id": "open_subscribe_member_view",
                "type": "button",
                "value": "",  # value 없음
            }
        ]
    )

    await sub_events.open_subscribe_member_view(
        ack=ack,
        body=body,
        say=AsyncMock(),
        client=fake_slack_client,
        user=user,
        service=service,
    )

    fake_slack_client.views_open.assert_awaited_once()
    service.create_subscription.assert_not_called()


@pytest.mark.asyncio
async def test_open_subscribe_member_view_with_value_processes_subscription(
    ack, fake_slack_client, factory
) -> None:
    """✅ action value 에 target_user_id → _process_user_subscription 후 모달 open."""
    user = factory.make_user(user_id="U_X")
    service = _make_service_with_no_subscriptions()
    service.get_only_user.return_value = factories.make_user(
        user_id="U_TARGET", channel_id="C_T"
    )

    body = make_action_body(
        actions=[
            {
                "action_id": "open_subscribe_member_view",
                "type": "button",
                "value": '{"target_user_id": "U_TARGET"}',
            }
        ]
    )

    await sub_events.open_subscribe_member_view(
        ack=ack,
        body=body,
        say=AsyncMock(),
        client=fake_slack_client,
        user=user,
        service=service,
    )

    service.create_subscription.assert_called_once()
    fake_slack_client.views_open.assert_awaited_once()


# ---------------------------------------------------------------------------
# subscribe_member
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_member_creates_and_updates_view(
    ack, fake_slack_client, factory
) -> None:
    """✅ selected_user 정상 → create_subscription + views_update."""
    user = factory.make_user(user_id="U_X")
    service = _make_service_with_no_subscriptions()
    service.get_only_user.return_value = factories.make_user(
        user_id="U_NEW", channel_id="C_NEW"
    )

    body = make_action_body(
        actions=[
            {
                "action_id": "subscribe_member",
                "type": "users_select",
                "selected_user": "U_NEW",
            }
        ],
        view={"id": "V_X"},
    )

    await sub_events.subscribe_member(
        ack=ack,
        body=body,
        say=AsyncMock(),
        client=fake_slack_client,
        user=user,
        service=service,
    )

    service.create_subscription.assert_called_once()
    fake_slack_client.views_update.assert_awaited_once()
    kwargs = fake_slack_client.views_update.await_args.kwargs
    assert kwargs["view_id"] == "V_X"


@pytest.mark.asyncio
async def test_subscribe_member_without_selected_user_returns_silently(
    ack, fake_slack_client, factory
) -> None:
    """🌀 selected_user 없음 → 그냥 ack 만 하고 종료."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()

    body = make_action_body(
        actions=[
            {
                "action_id": "subscribe_member",
                "type": "users_select",
                "selected_user": None,
            }
        ],
    )

    await sub_events.subscribe_member(
        ack=ack,
        body=body,
        say=AsyncMock(),
        client=fake_slack_client,
        user=user,
        service=service,
    )

    ack.assert_awaited_once()
    service.create_subscription.assert_not_called()
    fake_slack_client.views_update.assert_not_called()


@pytest.mark.asyncio
async def test_subscribe_member_self_shows_warning_message(
    ack, fake_slack_client, factory
) -> None:
    """⚠️ 자기 자신 선택 → views_update 의 모달에 경고 메시지가 들어간다."""
    user = factory.make_user(user_id="U_X")
    service = _make_service_with_no_subscriptions()

    body = make_action_body(
        actions=[
            {
                "action_id": "subscribe_member",
                "type": "users_select",
                "selected_user": "U_X",
            }
        ],
        view={"id": "V_X"},
    )

    await sub_events.subscribe_member(
        ack=ack,
        body=body,
        say=AsyncMock(),
        client=fake_slack_client,
        user=user,
        service=service,
    )

    rendered = fake_slack_client.views_update.await_args.kwargs["view"].to_dict()
    body_text = ""
    for b in rendered["blocks"]:
        if b.get("text"):
            body_text += b["text"].get("text", "")
        if b.get("type") == "context":
            for el in b.get("elements", []):
                body_text += el.get("text", "")
    assert "자기 자신은 구독할 수 없어요" in body_text
    service.create_subscription.assert_not_called()


# ---------------------------------------------------------------------------
# unsubscribe_member
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unsubscribe_member_cancels_and_updates_view(
    ack, fake_slack_client, factory
) -> None:
    """✅ subscription_id 로 cancel_subscription 호출 + views_update."""
    user = factory.make_user(user_id="U_X")
    service = _make_service_with_no_subscriptions()

    body = make_action_body(
        actions=[
            {
                "action_id": "unsubscribe_member",
                "type": "overflow",
                "selected_option": {"value": "sub_id_123"},
            }
        ],
        view={"id": "V_X"},
    )

    await sub_events.unsubscribe_member(
        ack=ack,
        body=body,
        client=fake_slack_client,
        say=AsyncMock(),
        user=user,
        service=service,
    )

    service.cancel_subscription.assert_called_once_with("sub_id_123")
    fake_slack_client.views_update.assert_awaited_once()


# ---------------------------------------------------------------------------
# open_subscription_permalink
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_subscription_permalink_only_acks(
    ack, fake_slack_client, factory
) -> None:
    """✅ 로깅용이라 ack 만 호출."""
    user = factory.make_user()
    service = MagicMock()

    await sub_events.open_subscription_permalink(
        ack=ack,
        body=make_action_body(),
        say=AsyncMock(),
        client=fake_slack_client,
        user=user,
        service=service,
    )

    ack.assert_awaited_once()
    fake_slack_client.assert_not_called()


# ---------------------------------------------------------------------------
# _get_subscribe_member_view — 구독 N명별 블록 구성
# ---------------------------------------------------------------------------


def test_subscribe_member_view_with_zero_subscriptions() -> None:
    """🌀 구독 0건 → 구독 목록 블록 없음."""
    service = MagicMock()
    service.fetch_subscriptions_by_user_id.return_value = []

    view = sub_events._get_subscribe_member_view(
        user_id="U_X", service=service
    )

    rendered = view.to_dict()
    body_text = "".join(
        b.get("text", {}).get("text", "")
        for b in rendered["blocks"]
        if b.get("text")
    )
    assert "현재 0명을 구독" in body_text
    assert "*구독 목록*" not in body_text


def test_subscribe_member_view_with_two_subscriptions_shows_list() -> None:
    """✅ 구독 2건 → '구독 목록' 헤더 + 각 멤버 블록."""
    service = MagicMock()
    service.fetch_subscriptions_by_user_id.return_value = [
        factories.make_subscription(target_user_id="U_A", created_at="2025-01-01 09:00:00"),
        factories.make_subscription(target_user_id="U_B", created_at="2025-02-15 09:00:00"),
    ]

    view = sub_events._get_subscribe_member_view(
        user_id="U_X", service=service
    )

    rendered = view.to_dict()
    body_text = "".join(
        b.get("text", {}).get("text", "")
        for b in rendered["blocks"]
        if b.get("text")
    )
    assert "현재 2명을 구독" in body_text
    assert "*구독 목록*" in body_text
    assert "<@U_A>" in body_text
    assert "<@U_B>" in body_text
    assert "2025년 01월 01일" in body_text
    assert "2025년 02월 15일" in body_text


def test_subscribe_member_view_with_message_shows_warning() -> None:
    """🌀 message 인자 있음 → 경고 컨텍스트 블록 포함."""
    service = MagicMock()
    service.fetch_subscriptions_by_user_id.return_value = []

    view = sub_events._get_subscribe_member_view(
        user_id="U_X",
        service=service,
        message="⚠️ 이미 구독한 멤버입니다.",
    )

    rendered = view.to_dict()
    context_text = ""
    for b in rendered["blocks"]:
        if b.get("type") == "context":
            for el in b.get("elements", []):
                context_text += el.get("text", "")
    assert "이미 구독한 멤버입니다" in context_text
