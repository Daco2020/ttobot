"""슬랙 community 이벤트 핸들러 테스트.

대상: app/slack/events/community.py
- handle_coffee_chat_message
- cancel_coffee_chat_proof_button
- submit_coffee_chat_proof_button
- submit_coffee_chat_proof_view
- paper_plane_command
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.exception import BotException
from app.slack.events import community as community_events
from test import factories
from test.slack.conftest import (
    make_action_body,
    make_command_body,
    make_message_body,
    make_view_body,
)


# ---------------------------------------------------------------------------
# handle_coffee_chat_message — 본문/스레드/subtype 분기
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_coffee_chat_message_top_level_sends_ephemeral(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock, mocker
) -> None:
    """✅ 일반(스레드 아님) 메시지 → 인증 안내 ephemeral 전송."""
    user = factory.make_user(user_id="U_X")
    body = make_message_body(
        user_id="U_X",
        channel_id=settings.COFFEE_CHAT_PROOF_CHANNEL,
        ts="1700000000.000100",
        thread_ts=None,
    )

    # asyncio.sleep(1) 봉쇄
    mocker.patch(
        "app.slack.events.community.asyncio.sleep", new=AsyncMock()
    )

    await community_events.handle_coffee_chat_message(
        ack=ack,
        body=body,
        say=say,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
        subtype=None,
        is_thread=False,
        ts="1700000000.000100",
    )

    fake_slack_client.chat_postEphemeral.assert_awaited_once()
    kwargs = fake_slack_client.chat_postEphemeral.await_args.kwargs
    assert kwargs["user"] == "U_X"
    assert kwargs["channel"] == settings.COFFEE_CHAT_PROOF_CHANNEL
    # 버튼 두 개 (안내 닫기 / 커피챗 인증) 가 포함되어야 함
    actions_block = next(b for b in kwargs["blocks"] if b.block_id is None and b.type == "actions")
    button_ids = [el.action_id for el in actions_block.elements]
    assert "cancel_coffee_chat_proof_button" in button_ids
    assert "submit_coffee_chat_proof_button" in button_ids


@pytest.mark.asyncio
async def test_handle_coffee_chat_message_thread_reply_grants_points(
    ack, say, fake_slack_client, factory, point_service_mock, mocker
) -> None:
    """✅ 답글 메시지 + 인증 가능 → reactions_add + 포인트 지급."""
    user = factory.make_user(user_id="U_REPLIER")
    service = MagicMock()
    service.check_coffee_chat_proof.return_value = None
    service.create_coffee_chat_proof.return_value = factories.make_coffee_chat_proof()

    point_service = MagicMock()
    point_service.grant_if_coffee_chat_verified.return_value = "포인트 지급 완료"

    mocker.patch(
        "app.slack.events.community.send_point_noti_message", new=AsyncMock()
    )

    body = make_message_body(
        user_id="U_REPLIER",
        channel_id=settings.COFFEE_CHAT_PROOF_CHANNEL,
        ts="1700000000.000200",
        thread_ts="1700000000.000100",
        text="후기입니다.",
    )

    await community_events.handle_coffee_chat_message(
        ack=ack,
        body=body,
        say=say,
        client=fake_slack_client,
        user=user,
        service=service,
        point_service=point_service,
        subtype=None,
        is_thread=True,
        ts="1700000000.000200",
    )

    service.check_coffee_chat_proof.assert_called_once()
    service.create_coffee_chat_proof.assert_called_once()
    fake_slack_client.reactions_add.assert_awaited_once()
    point_service.grant_if_coffee_chat_verified.assert_called_once_with(
        user_id="U_REPLIER"
    )


@pytest.mark.asyncio
async def test_handle_coffee_chat_message_thread_reply_already_verified_silent(
    ack, say, fake_slack_client, factory, point_service_mock
) -> None:
    """⚠️ check_coffee_chat_proof 가 BotException → 조용히 종료."""
    user = factory.make_user(user_id="U_REPLIER")
    service = MagicMock()
    service.check_coffee_chat_proof.side_effect = BotException("이미 인증")

    body = make_message_body(
        user_id="U_REPLIER",
        channel_id=settings.COFFEE_CHAT_PROOF_CHANNEL,
        ts="1700000000.000200",
        thread_ts="1700000000.000100",
    )

    # 예외가 외부로 전파되지 않아야 한다
    await community_events.handle_coffee_chat_message(
        ack=ack,
        body=body,
        say=say,
        client=fake_slack_client,
        user=user,
        service=service,
        point_service=point_service_mock,
        subtype=None,
        is_thread=True,
        ts="1700000000.000200",
    )

    service.create_coffee_chat_proof.assert_not_called()
    fake_slack_client.reactions_add.assert_not_called()


@pytest.mark.asyncio
async def test_handle_coffee_chat_message_thread_message_changed_ignored(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """⚠️ subtype=message_changed + 답글 → 아무 동작 없음."""
    user = factory.make_user(user_id="U_X")
    body = make_message_body(user_id="U_X", subtype="message_changed")

    await community_events.handle_coffee_chat_message(
        ack=ack,
        body=body,
        say=say,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
        subtype="message_changed",
        is_thread=True,
        ts="1700000000.000200",
    )

    fake_slack_client.reactions_add.assert_not_called()
    fake_slack_client.chat_postEphemeral.assert_not_called()


# ---------------------------------------------------------------------------
# cancel_coffee_chat_proof_button
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_coffee_chat_proof_button_deletes_ephemeral(
    ack, fake_slack_client, factory, slack_service, point_service_mock, mocker
) -> None:
    """✅ requests.post 로 ephemeral 메시지 삭제 요청 전송."""
    user = factory.make_user()
    body = make_action_body(
        action_id="cancel_coffee_chat_proof_button",
        response_url="https://hooks.slack.example/cancel",
    )

    requests_mock = mocker.patch(
        "app.slack.events.community.requests.post"
    )

    await community_events.cancel_coffee_chat_proof_button(
        ack=ack,
        body=body,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )

    ack.assert_awaited_once()
    requests_mock.assert_called_once()
    args, kwargs = requests_mock.call_args
    assert args[0] == "https://hooks.slack.example/cancel"
    assert kwargs["json"]["delete_original"] is True


# ---------------------------------------------------------------------------
# submit_coffee_chat_proof_button
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_coffee_chat_proof_button_opens_modal(
    ack, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """✅ 인증 모달 open + private_metadata 에 ephemeral_url 과 message_ts 가 들어감."""
    user = factory.make_user(user_id="U_X")
    body = make_action_body(
        action_id="submit_coffee_chat_proof_button",
        response_url="https://hooks.slack.example/submit",
        actions=[
            {
                "action_id": "submit_coffee_chat_proof_button",
                "type": "button",
                "value": "1700000000.000100",
            }
        ],
    )

    await community_events.submit_coffee_chat_proof_button(
        ack=ack,
        body=body,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )

    fake_slack_client.views_open.assert_awaited_once()
    view = fake_slack_client.views_open.await_args.kwargs["view"]
    assert view.callback_id == "submit_coffee_chat_proof_view"
    # private_metadata 는 JSON 문자열 (ephemeral_url, message_ts)
    import json
    metadata = json.loads(view.private_metadata)
    assert metadata["ephemeral_url"] == "https://hooks.slack.example/submit"
    assert metadata["message_ts"] == "1700000000.000100"


# ---------------------------------------------------------------------------
# submit_coffee_chat_proof_view
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_coffee_chat_proof_view_only_one_user_returns_errors(
    ack, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """⚠️ 본인만 선택 (1명) → ack(errors=...)"""
    user = factory.make_user(user_id="U_X")
    body = make_view_body(
        user_id="U_X",
        callback_id="submit_coffee_chat_proof_view",
        state_values={
            "participant": {"select": {"selected_users": ["U_X"]}}
        },
    )

    await community_events.submit_coffee_chat_proof_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        say=AsyncMock(),
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )

    ack.assert_awaited_once()
    kwargs = ack.await_args.kwargs
    assert kwargs["response_action"] == "errors"
    assert "participant" in kwargs["errors"]
    fake_slack_client.reactions_add.assert_not_called()


@pytest.mark.asyncio
async def test_submit_coffee_chat_proof_view_with_participants_grants_point(
    ack, fake_slack_client, factory, mocker
) -> None:
    """✅ 본인 + 1명 이상 → reaction + 포인트 + create_coffee_chat_proof + ephemeral 삭제."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()
    service.create_coffee_chat_proof.return_value = factories.make_coffee_chat_proof()
    point_service = MagicMock()
    point_service.grant_if_coffee_chat_verified.return_value = "포인트 지급"

    fake_slack_client.conversations_history.return_value = {
        "messages": [{"ts": "1700000000.000100", "text": "원본 메시지", "files": []}]
    }
    fake_slack_client.chat_postMessage.return_value = {"ts": "thread_ts_1"}

    requests_mock = mocker.patch(
        "app.slack.events.community.requests.post"
    )
    mocker.patch(
        "app.slack.events.community.send_point_noti_message", new=AsyncMock()
    )

    body = make_view_body(
        user_id="U_X",
        callback_id="submit_coffee_chat_proof_view",
        private_metadata=(
            '{"ephemeral_url":"https://hooks.slack.example/x",'
            '"message_ts":"1700000000.000100"}'
        ),
        state_values={
            "participant": {
                "select": {"selected_users": ["U_X", "U_OTHER1", "U_OTHER2"]}
            }
        },
    )

    await community_events.submit_coffee_chat_proof_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        say=AsyncMock(),
        user=user,
        service=service,
        point_service=point_service,
    )

    fake_slack_client.reactions_add.assert_awaited_once()
    point_service.grant_if_coffee_chat_verified.assert_called_once_with(user_id="U_X")
    # 참여자 호출 메시지 + create_coffee_chat_proof
    fake_slack_client.chat_postMessage.assert_awaited_once()
    posted_text = fake_slack_client.chat_postMessage.await_args.kwargs["text"]
    assert "<@U_OTHER1>" in posted_text
    assert "<@U_OTHER2>" in posted_text
    # 본인은 제외되어야 함
    assert "<@U_X>" not in posted_text
    service.create_coffee_chat_proof.assert_called_once()
    cc_kwargs = service.create_coffee_chat_proof.call_args.kwargs
    assert cc_kwargs["user_id"] == "U_X"
    assert cc_kwargs["selected_user_ids"] == "U_OTHER1,U_OTHER2"  # 본인 제외
    assert cc_kwargs["participant_call_thread_ts"] == "thread_ts_1"
    # ephemeral 삭제
    requests_mock.assert_called_once()


@pytest.mark.asyncio
async def test_submit_coffee_chat_proof_view_only_self_among_others(
    ack, fake_slack_client, factory, mocker
) -> None:
    """🌀 본인 + 1명 (총 2명) 선택 → 호출 메시지가 1명만 호출."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()
    service.create_coffee_chat_proof.return_value = factories.make_coffee_chat_proof()
    point_service = MagicMock()
    point_service.grant_if_coffee_chat_verified.return_value = "포인트 지급"

    fake_slack_client.conversations_history.return_value = {
        "messages": [{"ts": "1700000000.000100", "text": "x", "files": []}]
    }
    fake_slack_client.chat_postMessage.return_value = {"ts": "thread_ts_1"}

    mocker.patch("app.slack.events.community.requests.post")
    mocker.patch(
        "app.slack.events.community.send_point_noti_message", new=AsyncMock()
    )

    body = make_view_body(
        user_id="U_X",
        callback_id="submit_coffee_chat_proof_view",
        private_metadata=(
            '{"ephemeral_url":"https://hooks.slack.example/x",'
            '"message_ts":"1700000000.000100"}'
        ),
        state_values={
            "participant": {"select": {"selected_users": ["U_X", "U_OTHER"]}}
        },
    )

    await community_events.submit_coffee_chat_proof_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        say=AsyncMock(),
        user=user,
        service=service,
        point_service=point_service,
    )

    posted_text = fake_slack_client.chat_postMessage.await_args.kwargs["text"]
    assert "<@U_OTHER>" in posted_text
    assert "<@U_X>" not in posted_text


# ---------------------------------------------------------------------------
# /종이비행기 (paper_plane_command)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_paper_plane_command_for_super_admin(
    ack, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """🌀 SUPER_ADMIN → 무한(∞) 표시."""
    user = factory.make_user(user_id=settings.SUPER_ADMIN, name="슈퍼")
    await community_events.paper_plane_command(
        ack=ack,
        body=make_command_body(user_id=settings.SUPER_ADMIN, command="/종이비행기"),
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )

    fake_slack_client.views_open.assert_awaited_once()
    view = fake_slack_client.views_open.await_args.kwargs["view"]
    rendered = view.to_dict()
    body_text = "".join(
        b.get("text", {}).get("text", "")
        for b in rendered["blocks"]
        if b.get("text")
    ) + "".join(
        el.get("text", "")
        for b in rendered["blocks"]
        if b.get("type") == "context"
        for el in b.get("elements", [])
    )
    assert "∞" in body_text


@pytest.mark.asyncio
async def test_paper_plane_command_for_regular_user_currently_unlimited(
    ack, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """🌀 일반 유저도 현재 코드 상 무한(∞) 표시 (주석 처리되어 있음)."""
    user = factory.make_user(user_id="U_REG", name="일반유저")
    await community_events.paper_plane_command(
        ack=ack,
        body=make_command_body(user_id="U_REG", command="/종이비행기"),
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )

    view = fake_slack_client.views_open.await_args.kwargs["view"]
    rendered = view.to_dict()
    body_text = "".join(
        el.get("text", "")
        for b in rendered["blocks"]
        if b.get("type") == "context"
        for el in b.get("elements", [])
    )
    assert "∞" in body_text
    # 주요 버튼들이 노출되는지 확인
    button_ids: list[str] = []
    for b in rendered["blocks"]:
        if b.get("type") == "actions":
            for el in b.get("elements", []):
                if "action_id" in el:
                    button_ids.append(el["action_id"])
    assert "send_paper_plane_message" in button_ids
    assert "open_paper_plane_url" in button_ids
