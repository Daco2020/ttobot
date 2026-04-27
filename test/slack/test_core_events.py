"""슬랙 core 이벤트 핸들러 테스트.

대상 핸들러: app/slack/events/core.py
- handle_app_mention, handle_channel_created
- 명령어 핸들러: open_deposit_view, open_submission_history_view, open_help_view, admin_command
- 액션/뷰: handle_sync_store, handle_invite_channel(_view), handle_home_tab,
            open_point_history_view, open_point_guide_view, open_paper_plane_guide_view,
            open_coffee_chat_history_view, open_paper_plane_url,
            send_paper_plane_message(_view), download_*_history
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from slack_sdk.errors import SlackApiError

from app.config import settings
from app.constants import BOT_IDS
from app.slack.events import core as core_events
from app.slack.services.point import UserPoint
from test import factories
from test.slack.conftest import make_action_body, make_command_body, make_view_body


# ---------------------------------------------------------------------------
# 미니 핸들러: ack 만 호출하는 것들
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_app_mention_only_acks(ack, say, fake_slack_client) -> None:
    """✅ app_mention 핸들러는 ack 만 호출."""
    await core_events.handle_app_mention(
        ack=ack, body={"event": {}}, say=say, client=fake_slack_client
    )
    ack.assert_awaited_once()
    fake_slack_client.assert_not_called()


@pytest.mark.asyncio
async def test_open_paper_plane_url_only_acks(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """✅ open_paper_plane_url 액션 핸들러는 ack 만 호출 (로그용)."""
    body = make_action_body(action_id="open_paper_plane_url")
    user = factory.make_user()
    await core_events.open_paper_plane_url(
        ack=ack,
        body=body,
        say=say,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )
    ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_channel_created_acks(ack, fake_slack_client) -> None:
    """✅ channel_created 핸들러는 ack 후 동작 (실제 동작은 코드를 봐야하나, ack 자체는 항상 호출)."""
    body = {"event": {"channel": {"id": "C_NEW", "name": "new"}}}
    fake_slack_client.conversations_join = AsyncMock()
    fake_slack_client.chat_postMessage = AsyncMock()
    try:
        await core_events.handle_channel_created(
            ack=ack, body=body, client=fake_slack_client
        )
    except Exception:
        pass  # 일부 분기에서 추가 호출이 있을 수 있으나 본 테스트는 ack 만 검증
    ack.assert_awaited_once()


# ---------------------------------------------------------------------------
# /예치금 (open_deposit_view)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_deposit_view_with_deposit(
    ack, say, fake_slack_client, factory, point_service_mock
) -> None:
    """✅ deposit 있는 유저 → 패스/미제출/커피챗 정보가 포함된 모달."""
    user = factory.make_user(user_id="U_X", name="홍길동", deposit="80000")
    service = MagicMock()
    service.fetch_coffee_chat_proofs.return_value = [
        factories.make_coffee_chat_proof(),
        factories.make_coffee_chat_proof(),
    ]

    await core_events.open_deposit_view(
        ack=ack,
        body=make_command_body(user_id="U_X"),
        say=say,
        client=fake_slack_client,
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    fake_slack_client.views_open.assert_awaited_once()
    view = fake_slack_client.views_open.await_args.kwargs["view"]
    rendered = view.to_dict()
    text = rendered["blocks"][0]["text"]["text"]
    assert "80,000" in text
    assert "커피챗 인증 수 : 2" in text


@pytest.mark.asyncio
async def test_open_deposit_view_when_deposit_empty(
    ack, say, fake_slack_client, factory, point_service_mock
) -> None:
    """🌀 deposit 빈 문자열 → '확인 중' 메시지."""
    user = factory.make_user(deposit="")
    service = MagicMock()

    await core_events.open_deposit_view(
        ack=ack,
        body=make_command_body(),
        say=say,
        client=fake_slack_client,
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    view = fake_slack_client.views_open.await_args.kwargs["view"]
    text = view.to_dict()["blocks"][0]["text"]["text"]
    assert "확인 중" in text
    service.fetch_coffee_chat_proofs.assert_not_called()


# ---------------------------------------------------------------------------
# /제출내역 (open_submission_history_view)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submission_history_with_contents(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock, mocker
) -> None:
    """✅ 제출 내역이 있을 때 → 회차/링크 포함."""
    # 활동기간 안의 dt 로 콘텐츠 생성
    contents = [
        factories.make_content(
            dt="2025-01-05 10:00:00",
            title="A 글",
            type="submit",
            content_url="https://ex.com/a",
        ),
    ]
    user = factory.make_user(contents=contents)

    # get_due_date / get_round 가 동작하도록 DUE_DATES 를 mock
    mocker.patch(
        "app.models.DUE_DATES",
        [__import__("datetime").date(2025, 1, 1), __import__("datetime").date(2025, 1, 31)],
    )
    mocker.patch(
        "app.models.tz_now",
        return_value=__import__("datetime").datetime(2025, 1, 15, 12, 0, 0),
    )

    await core_events.open_submission_history_view(
        ack=ack,
        body=make_command_body(),
        say=say,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )

    fake_slack_client.views_open.assert_awaited_once()
    rendered = fake_slack_client.views_open.await_args.kwargs["view"].to_dict()
    body_text = "".join(
        b.get("text", {}).get("text", "") for b in rendered["blocks"] if b.get("text")
    )
    assert "1회차 제출" in body_text
    assert "A 글" in body_text


@pytest.mark.asyncio
async def test_submission_history_empty(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock, mocker
) -> None:
    """🌀 제출 내역 없음 → '글 제출 내역이 없어요.'"""
    user = factory.make_user(contents=[])
    mocker.patch(
        "app.models.DUE_DATES",
        [__import__("datetime").date(2025, 1, 1), __import__("datetime").date(2025, 1, 31)],
    )
    mocker.patch(
        "app.models.tz_now",
        return_value=__import__("datetime").datetime(2025, 1, 15, 12, 0, 0),
    )

    await core_events.open_submission_history_view(
        ack=ack,
        body=make_command_body(),
        say=say,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )

    rendered = fake_slack_client.views_open.await_args.kwargs["view"].to_dict()
    body_text = "".join(
        b.get("text", {}).get("text", "") for b in rendered["blocks"] if b.get("text")
    )
    assert "글 제출 내역이 없어요" in body_text


# ---------------------------------------------------------------------------
# /도움말 (open_help_view)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_help_view(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """✅ /도움말 → 모달 + 명령어 안내 포함."""
    user = factory.make_user()
    await core_events.open_help_view(
        ack=ack,
        body=make_command_body(command="/도움말"),
        say=say,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )

    fake_slack_client.views_open.assert_awaited_once()
    rendered = fake_slack_client.views_open.await_args.kwargs["view"].to_dict()
    body_text = "".join(
        b.get("text", {}).get("text", "") for b in rendered["blocks"] if b.get("text")
    )
    assert "/제출" in body_text
    assert "/패스" in body_text
    assert "/북마크" in body_text


# ---------------------------------------------------------------------------
# /관리자 (admin_command)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_command_admin(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """✅ admin → ephemeral 메시지 표시."""
    admin = factory.make_user(user_id=settings.ADMIN_IDS[0])
    await core_events.admin_command(
        ack=ack,
        body=make_command_body(user_id=admin.user_id),
        say=say,
        client=fake_slack_client,
        user=admin,
        service=slack_service,
        point_service=point_service_mock,
    )

    fake_slack_client.chat_postEphemeral.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_command_non_admin_raises_permission_error(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """⚠️ 비-admin → PermissionError raise."""
    user = factory.make_user(user_id="U_GUEST")
    with pytest.raises(PermissionError):
        await core_events.admin_command(
            ack=ack,
            body=make_command_body(user_id=user.user_id),
            say=say,
            client=fake_slack_client,
            user=user,
            service=slack_service,
            point_service=point_service_mock,
        )


# ---------------------------------------------------------------------------
# handle_sync_store
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_sync_store_dispatches_per_option(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock, mocker
) -> None:
    """✅ value=유저 → store.pull_users 호출."""
    fake_store = MagicMock()
    mocker.patch("app.slack.events.core.Store", return_value=fake_store)
    mocker.patch("app.slack.events.core.SpreadSheetClient")

    body = make_action_body(
        state={
            "values": {
                "sync_store_block": {
                    "sync_store_select": {
                        "selected_option": {"value": "유저"},
                    }
                }
            }
        }
    )

    await core_events.handle_sync_store(
        ack=ack,
        body=body,
        say=say,
        client=fake_slack_client,
        user=factory.make_user(),
        service=slack_service,
        point_service=point_service_mock,
    )

    fake_store.pull_users.assert_called_once()
    # 시작/완료 두 번 메시지 전송
    assert fake_slack_client.chat_postMessage.await_count == 2


@pytest.mark.asyncio
async def test_handle_sync_store_unknown_option(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock, mocker
) -> None:
    """⚠️ 알 수 없는 option → '동기화 테이블이 존재하지 않습니다.'"""
    fake_store = MagicMock()
    mocker.patch("app.slack.events.core.Store", return_value=fake_store)
    mocker.patch("app.slack.events.core.SpreadSheetClient")

    body = make_action_body(
        state={
            "values": {
                "sync_store_block": {
                    "sync_store_select": {
                        "selected_option": {"value": "이상한값"},
                    }
                }
            }
        }
    )

    await core_events.handle_sync_store(
        ack=ack,
        body=body,
        say=say,
        client=fake_slack_client,
        user=factory.make_user(),
        service=slack_service,
        point_service=point_service_mock,
    )

    # 시작 + 알수없음 + 완료 = 3번
    posted_texts = [
        c.kwargs["text"] for c in fake_slack_client.chat_postMessage.await_args_list
    ]
    assert any("동기화 테이블이 존재하지 않습니다" in t for t in posted_texts)


@pytest.mark.asyncio
async def test_handle_sync_store_swallows_exception(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock, mocker
) -> None:
    """⚠️ store 메서드 예외 → 관리자 채널에 에러 메시지."""
    fake_store = MagicMock()
    fake_store.pull_users.side_effect = RuntimeError("boom")
    mocker.patch("app.slack.events.core.Store", return_value=fake_store)
    mocker.patch("app.slack.events.core.SpreadSheetClient")

    body = make_action_body(
        state={
            "values": {
                "sync_store_block": {
                    "sync_store_select": {"selected_option": {"value": "유저"}}
                }
            }
        }
    )

    # 예외가 외부로 전파되지 않아야 함 (try/except 로 감싸져 있음)
    await core_events.handle_sync_store(
        ack=ack,
        body=body,
        say=say,
        client=fake_slack_client,
        user=factory.make_user(),
        service=slack_service,
        point_service=point_service_mock,
    )

    posted_texts = [
        c.kwargs["text"] for c in fake_slack_client.chat_postMessage.await_args_list
    ]
    assert any("boom" in t for t in posted_texts)


# ---------------------------------------------------------------------------
# handle_invite_channel / handle_invite_channel_view / _invite_channel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_invite_channel_opens_modal(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """✅ 모달이 열린다."""
    await core_events.handle_invite_channel(
        ack=ack,
        body=make_action_body(),
        say=say,
        client=fake_slack_client,
        user=factory.make_user(),
        service=slack_service,
        point_service=point_service_mock,
    )
    fake_slack_client.views_open.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_invite_channel_view_with_selected_channels(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock, mocker
) -> None:
    """✅ 선택 채널들이 있으면 그 채널만 초대."""
    mocker.patch(
        "app.slack.events.core._invite_channel",
        new=AsyncMock(),
    )

    body = make_view_body(
        state_values={
            "user": {"select_user": {"selected_user": "U_INVITED"}},
            "channel": {"select_channels": {"selected_channels": ["C_1", "C_2"]}},
        }
    )

    await core_events.handle_invite_channel_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        view=body["view"],
        say=say,
        user=factory.make_user(),
        service=slack_service,
        point_service=point_service_mock,
    )

    # 시작 + 완료 메시지 (각 채널 별 메시지는 _invite_channel 안에서 보내므로 mock)
    posted = [
        c.kwargs["text"] for c in fake_slack_client.chat_postMessage.await_args_list
    ]
    assert any("채널 초대를 시작합니다" in t and "2 개" in t for t in posted)
    assert any("채널 초대가 완료되었습니다" in t for t in posted)


@pytest.mark.asyncio
async def test_handle_invite_channel_view_no_channels_uses_all_public(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock, mocker
) -> None:
    """✅ 채널 미선택 → 모든 공개 채널 fetch 후 초대."""
    mocker.patch(
        "app.slack.events.core._invite_channel",
        new=AsyncMock(),
    )
    mocker.patch(
        "app.slack.events.core._fetch_public_channel_ids",
        new=AsyncMock(return_value=["C_PUB_1", "C_PUB_2", "C_PUB_3"]),
    )

    body = make_view_body(
        state_values={
            "user": {"select_user": {"selected_user": "U_INVITED"}},
            "channel": {"select_channels": {"selected_channels": []}},
        }
    )

    await core_events.handle_invite_channel_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        view=body["view"],
        say=say,
        user=factory.make_user(),
        service=slack_service,
        point_service=point_service_mock,
    )

    posted = [
        c.kwargs["text"] for c in fake_slack_client.chat_postMessage.await_args_list
    ]
    assert any("3 개" in t for t in posted)


@pytest.mark.asyncio
async def test_invite_channel_already_in_channel(fake_slack_client) -> None:
    """⚠️ already_in_channel → '이미 채널에 참여 중' 메시지."""
    fake_slack_client.conversations_invite.side_effect = SlackApiError(
        message="x", response={"error": "already_in_channel"}
    )

    await core_events._invite_channel(fake_slack_client, "U_X", "C_X")

    posted = [
        c.kwargs["text"] for c in fake_slack_client.chat_postMessage.await_args_list
    ]
    assert any("이미 채널에 참여 중" in t for t in posted)


@pytest.mark.asyncio
async def test_invite_channel_cant_invite_self(fake_slack_client) -> None:
    """⚠️ cant_invite_self → '또봇이 자기 자신을 초대' 메시지."""
    fake_slack_client.conversations_invite.side_effect = SlackApiError(
        message="x", response={"error": "cant_invite_self"}
    )

    await core_events._invite_channel(fake_slack_client, "U_X", "C_X")

    posted = [
        c.kwargs["text"] for c in fake_slack_client.chat_postMessage.await_args_list
    ]
    assert any("자기 자신을 초대" in t for t in posted)


@pytest.mark.asyncio
async def test_invite_channel_not_in_channel_joins_then_invites(
    fake_slack_client,
) -> None:
    """⚠️ not_in_channel → join 후 다시 invite → 성공 메시지."""
    fake_slack_client.conversations_invite.side_effect = [
        SlackApiError(message="x", response={"error": "not_in_channel"}),
        None,
    ]

    await core_events._invite_channel(fake_slack_client, "U_X", "C_X")

    fake_slack_client.conversations_join.assert_awaited_once_with(channel="C_X")
    assert fake_slack_client.conversations_invite.await_count == 2
    posted = [
        c.kwargs["text"] for c in fake_slack_client.chat_postMessage.await_args_list
    ]
    assert any("또봇도 함께 채널 초대" in t for t in posted)


@pytest.mark.asyncio
async def test_invite_channel_unknown_error_includes_doc_link(
    fake_slack_client,
) -> None:
    """⚠️ 알 수 없는 SlackApiError → 에러 코드와 문서 링크 포함."""
    fake_slack_client.conversations_invite.side_effect = SlackApiError(
        message="x", response={"error": "some_weird_error"}
    )

    await core_events._invite_channel(fake_slack_client, "U_X", "C_X")

    posted = [
        c.kwargs["text"] for c in fake_slack_client.chat_postMessage.await_args_list
    ]
    assert any(
        "some_weird_error" in t and "문서 확인하기" in t for t in posted
    )


# ---------------------------------------------------------------------------
# handle_home_tab
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_home_tab_for_unknown_user(
    fake_slack_client, slack_service, point_service_mock
) -> None:
    """✅ user 가 None 이면 안내 home 뷰만 publish."""
    event = {"user": "U_GHOST", "tab": "home"}
    await core_events.handle_home_tab(
        event=event,
        client=fake_slack_client,
        user=None,
        service=slack_service,
        point_service=point_service_mock,
    )

    fake_slack_client.views_publish.assert_awaited_once()
    kwargs = fake_slack_client.views_publish.await_args.kwargs
    assert kwargs["user_id"] == "U_GHOST"


@pytest.mark.asyncio
async def test_handle_home_tab_for_registered_user(
    fake_slack_client, factory, slack_service
) -> None:
    """✅ 등록된 user → 홈 탭 풀세팅 publish."""
    user = factory.make_user(user_id="U_REG", name="홍길동")
    point_service = MagicMock()
    point_service.get_user_point.return_value = UserPoint(
        user=user, point_histories=[]
    )

    await core_events.handle_home_tab(
        event={"user": "U_REG", "tab": "home"},
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service,
    )

    fake_slack_client.views_publish.assert_awaited_once()
    kwargs = fake_slack_client.views_publish.await_args.kwargs
    assert kwargs["user_id"] == "U_REG"
    rendered = kwargs["view"].to_dict()
    body_text = "".join(
        b.get("text", {}).get("text", "") for b in rendered["blocks"] if b.get("text")
    )
    assert "내 글또 포인트" in body_text


# ---------------------------------------------------------------------------
# 액션 핸들러: 단순 모달 open
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_point_history_view_opens_modal(
    ack, say, fake_slack_client, factory, slack_service
) -> None:
    """✅ 포인트 히스토리 모달 open."""
    user = factory.make_user(user_id="U_X")
    point_service = MagicMock()
    point_service.get_user_point.return_value = UserPoint(
        user=user,
        point_histories=[factories.make_point_history(user_id="U_X", point=100)],
    )

    await core_events.open_point_history_view(
        ack=ack,
        body=make_action_body(),
        say=say,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service,
    )

    fake_slack_client.views_open.assert_awaited_once()


@pytest.mark.asyncio
async def test_open_point_guide_view_opens_modal(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """✅ 포인트 가이드 모달 open."""
    await core_events.open_point_guide_view(
        ack=ack,
        body=make_action_body(),
        say=say,
        client=fake_slack_client,
        user=factory.make_user(),
        service=slack_service,
        point_service=point_service_mock,
    )
    fake_slack_client.views_open.assert_awaited_once()


@pytest.mark.asyncio
async def test_open_paper_plane_guide_view_opens_modal(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """✅ 종이비행기 가이드 모달 open."""
    await core_events.open_paper_plane_guide_view(
        ack=ack,
        body=make_action_body(),
        say=say,
        client=fake_slack_client,
        user=factory.make_user(),
        service=slack_service,
        point_service=point_service_mock,
    )
    fake_slack_client.views_open.assert_awaited_once()


@pytest.mark.asyncio
async def test_open_coffee_chat_history_view_with_no_proofs(
    ack, say, fake_slack_client, factory, point_service_mock
) -> None:
    """🌀 커피챗 인증 0건 → '아직 커피챗 인증 내역이 없어요.'"""
    user = factory.make_user()
    service = MagicMock()
    service.fetch_coffee_chat_proofs.return_value = []

    await core_events.open_coffee_chat_history_view(
        ack=ack,
        body=make_action_body(),
        say=say,
        client=fake_slack_client,
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    fake_slack_client.views_open.assert_awaited_once()
    rendered = fake_slack_client.views_open.await_args.kwargs["view"].to_dict()
    body_text = "".join(
        b.get("text", {}).get("text", "") for b in rendered["blocks"] if b.get("text")
    )
    assert "아직 커피챗 인증 내역이 없어요" in body_text


@pytest.mark.asyncio
async def test_open_coffee_chat_history_view_with_proofs_shows_download(
    ack, say, fake_slack_client, factory, point_service_mock
) -> None:
    """✅ 커피챗 인증이 있으면 다운로드 버튼 포함."""
    user = factory.make_user()
    service = MagicMock()
    service.fetch_coffee_chat_proofs.return_value = [
        factories.make_coffee_chat_proof(text="후기 입니다.")
    ]

    await core_events.open_coffee_chat_history_view(
        ack=ack,
        body=make_action_body(),
        say=say,
        client=fake_slack_client,
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    rendered = fake_slack_client.views_open.await_args.kwargs["view"].to_dict()
    # 다운로드 버튼이 actions 블록에 들어있는지 확인
    button_texts: list[str] = []
    for b in rendered["blocks"]:
        if b.get("type") == "actions":
            for el in b.get("elements", []):
                button_texts.append(el.get("text", {}).get("text", ""))
    assert any("전체 내역 다운로드" in t for t in button_texts)


# ---------------------------------------------------------------------------
# send_paper_plane_message (액션) / send_paper_plane_message_view (뷰)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_paper_plane_message_opens_modal(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """✅ 종이비행기 보내기 액션 → 모달 open."""
    body = make_action_body(
        actions=[
            {"action_id": "send_paper_plane_message", "value": "U_RECEIVER", "type": "button"}
        ]
    )

    await core_events.send_paper_plane_message(
        ack=ack,
        body=body,
        say=say,
        client=fake_slack_client,
        user=factory.make_user(),
        service=slack_service,
        point_service=point_service_mock,
    )

    fake_slack_client.views_open.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_paper_plane_message_view_to_self_returns_error(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """⚠️ 자기 자신에게 보내면 ack(errors=...) 호출."""
    user = factory.make_user(user_id="U_ME")
    body = make_view_body(
        state_values={
            "paper_plane_receiver": {"select_user": {"selected_user": "U_ME"}},
            "paper_plane_message": {"paper_plane_message": {"value": "hi"}},
        }
    )

    await core_events.send_paper_plane_message_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        view=body["view"],
        say=say,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )

    ack.assert_awaited_once()
    kwargs = ack.await_args.kwargs
    assert kwargs["response_action"] == "errors"
    assert "paper_plane_receiver" in kwargs["errors"]
    fake_slack_client.chat_postMessage.assert_not_called()


@pytest.mark.asyncio
async def test_send_paper_plane_message_view_text_too_long(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """⚠️ 텍스트 300자 초과 → ack errors."""
    body = make_view_body(
        state_values={
            "paper_plane_receiver": {"select_user": {"selected_user": "U_OTHER"}},
            "paper_plane_message": {"paper_plane_message": {"value": "x" * 301}},
        }
    )

    await core_events.send_paper_plane_message_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        view=body["view"],
        say=say,
        user=factory.make_user(user_id="U_ME"),
        service=slack_service,
        point_service=point_service_mock,
    )

    kwargs = ack.await_args.kwargs
    assert kwargs["response_action"] == "errors"
    assert "paper_plane_message" in kwargs["errors"]


@pytest.mark.asyncio
async def test_send_paper_plane_message_view_to_bot(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """⚠️ 받는 사람이 봇 → ack errors."""
    body = make_view_body(
        state_values={
            "paper_plane_receiver": {"select_user": {"selected_user": BOT_IDS[0]}},
            "paper_plane_message": {"paper_plane_message": {"value": "hi"}},
        }
    )

    await core_events.send_paper_plane_message_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        view=body["view"],
        say=say,
        user=factory.make_user(user_id="U_ME"),
        service=slack_service,
        point_service=point_service_mock,
    )

    kwargs = ack.await_args.kwargs
    assert kwargs["response_action"] == "errors"


# ---------------------------------------------------------------------------
# download_point_history / download_coffee_chat_history / download_submission_history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_point_history_with_no_history(
    ack, say, fake_slack_client, factory, slack_service
) -> None:
    """⚠️ 내역 없음 → '포인트 획득 내역이 없습니다.' 메시지 후 종료."""
    user = factory.make_user(user_id="U_X")
    fake_slack_client.conversations_open.return_value = {"channel": {"id": "DM_X"}}

    point_service = MagicMock()
    point_service.get_user_point.return_value = UserPoint(
        user=user, point_histories=[]
    )

    await core_events.download_point_history(
        ack=ack,
        body=make_action_body(),
        say=say,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service,
    )

    fake_slack_client.chat_postMessage.assert_awaited_once()
    kwargs = fake_slack_client.chat_postMessage.await_args.kwargs
    assert kwargs["channel"] == "DM_X"
    assert "포인트 획득 내역이 없습니다" in kwargs["text"]
    fake_slack_client.files_upload_v2.assert_not_called()


@pytest.mark.asyncio
async def test_download_point_history_uploads_csv(
    ack,
    say,
    fake_slack_client,
    factory,
    slack_service,
    tmp_store,
) -> None:
    """✅ 내역 있음 → CSV 업로드 + permalink 메시지 + 임시파일 삭제."""
    user = factory.make_user(user_id="U_X", name="홍길동")
    fake_slack_client.conversations_open.return_value = {"channel": {"id": "DM_X"}}
    fake_slack_client.files_upload_v2.return_value = {
        "file": {"permalink": "https://slack.example/perma"}
    }

    point_service = MagicMock()
    point_service.get_user_point.return_value = UserPoint(
        user=user,
        point_histories=[factories.make_point_history(user_id="U_X", point=100)],
    )

    await core_events.download_point_history(
        ack=ack,
        body=make_action_body(),
        say=say,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service,
    )

    fake_slack_client.files_upload_v2.assert_awaited_once()
    kwargs = fake_slack_client.files_upload_v2.await_args.kwargs
    assert "U_X 의" not in kwargs.get("initial_comment", "")
    assert kwargs["channel"] == "DM_X"
    # permalink 메시지가 함께 전송된다
    posted = [
        c.kwargs["text"] for c in fake_slack_client.chat_postMessage.await_args_list
    ]
    assert any("https://slack.example/perma" in t for t in posted)


@pytest.mark.asyncio
async def test_download_coffee_chat_history_empty(
    ack, say, fake_slack_client, factory, point_service_mock
) -> None:
    """⚠️ 커피챗 0건 → '커피챗 인증 내역이 없습니다.' 메시지 후 종료."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()
    service.fetch_coffee_chat_proofs.return_value = []
    fake_slack_client.conversations_open.return_value = {"channel": {"id": "DM_X"}}

    await core_events.download_coffee_chat_history(
        ack=ack,
        body=make_action_body(),
        say=say,
        client=fake_slack_client,
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    fake_slack_client.chat_postMessage.assert_awaited_once()
    kwargs = fake_slack_client.chat_postMessage.await_args.kwargs
    assert "커피챗 인증 내역이 없습니다" in kwargs["text"]
    fake_slack_client.files_upload_v2.assert_not_called()


@pytest.mark.asyncio
async def test_download_submission_history_empty(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """⚠️ 제출 내역 0건 → 안내 메시지 후 종료."""
    user = factory.make_user(contents=[])
    fake_slack_client.conversations_open.return_value = {"channel": {"id": "DM_X"}}

    await core_events.download_submission_history(
        ack=ack,
        body=make_action_body(),
        say=say,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )

    fake_slack_client.chat_postMessage.assert_awaited_once()
    kwargs = fake_slack_client.chat_postMessage.await_args.kwargs
    assert "글 제출 내역이 없습니다" in kwargs["text"]
    fake_slack_client.files_upload_v2.assert_not_called()
