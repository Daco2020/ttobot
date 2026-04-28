"""슬랙 log 이벤트 핸들러 테스트.

대상: app/slack/events/log.py
- handle_comment_data, handle_post_data
- handle_reaction_added (공지/성윤글 포인트 분기 다수)
- handle_reaction_removed
- _is_thread_message (캐시 적용된 외부 호출 헬퍼)
- _is_checked_notice / _write_checked_notice
- _is_checked_super_admin_post / _write_checked_super_admin_post
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.constants import PRIMARY_CHANNEL
from app.slack.events import log as log_events
from test import factories
from test.slack.conftest import make_message_body, make_reaction_body


# ---------------------------------------------------------------------------
# handle_comment_data / handle_post_data — BigQuery 큐 적재
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_comment_data_appends_to_queue(mocker) -> None:
    """✅ comments_upload_queue 에 정확한 dict push."""
    queue = mocker.patch(
        "app.slack.events.log.bigquery_queue.comments_upload_queue", new=[]
    )

    body = make_message_body(
        user_id="U_X",
        channel_id="C_X",
        ts="1700000000.000200",
        thread_ts="1700000000.000100",
        text="댓글 내용",
    )

    await log_events.handle_comment_data(body=body)

    assert len(queue) == 1
    item = queue[0]
    assert item["user_id"] == "U_X"
    assert item["channel_id"] == "C_X"
    assert item["ts"] == "1700000000.000100"  # thread_ts (상위 메시지)
    assert item["comment_ts"] == "1700000000.000200"
    assert item["text"] == "댓글 내용"
    # tddate 와 createtime 은 ts 로 변환된 datetime/date
    assert item["tddate"] == datetime.fromtimestamp(float("1700000000.000200")).date()


@pytest.mark.asyncio
async def test_handle_post_data_appends_to_queue(mocker) -> None:
    """✅ posts_upload_queue 에 정확한 dict push."""
    queue = mocker.patch(
        "app.slack.events.log.bigquery_queue.posts_upload_queue", new=[]
    )

    body = make_message_body(
        user_id="U_X",
        channel_id="C_X",
        ts="1700000000.000200",
        text="게시글 내용",
    )

    await log_events.handle_post_data(body=body)

    assert len(queue) == 1
    item = queue[0]
    assert item["user_id"] == "U_X"
    assert item["channel_id"] == "C_X"
    assert item["ts"] == "1700000000.000200"
    assert item["text"] == "게시글 내용"


# ---------------------------------------------------------------------------
# handle_reaction_added — 일반 리액션 (공지/성윤 분기 외)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_reaction_added_general_only_appends_emoji_queue(
    ack, fake_slack_client, mocker
) -> None:
    """✅ 공지/성윤 분기에 해당하지 않는 리액션 → emoji 큐에만 적재."""
    emoji_queue = mocker.patch(
        "app.slack.events.log.bigquery_queue.emojis_upload_queue", new=[]
    )

    body = make_reaction_body(
        user_id="U_REACT",
        channel_id="C_RANDOM",  # 공지/PRIMARY 채널 아님
        item_ts="1700000000.000200",
        reaction="thumbsup",
    )

    await log_events.handle_reaction_added(
        ack=ack, body=body, client=fake_slack_client
    )

    assert len(emoji_queue) == 1
    assert emoji_queue[0]["user_id"] == "U_REACT"
    assert emoji_queue[0]["reaction"] == "thumbsup"
    fake_slack_client.chat_postMessage.assert_not_called()


# ---------------------------------------------------------------------------
# handle_reaction_added — 공지 채널 + noti-check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_reaction_added_notice_grants_point_first_time(
    ack, fake_slack_client, mocker, tmp_store
) -> None:
    """✅ 공지 채널 + noti-check + 첫 확인 + 3일 이내 → 포인트 지급 + 기록 저장."""
    mocker.patch(
        "app.slack.events.log.bigquery_queue.emojis_upload_queue", new=[]
    )
    # 스레드 아닌 일반 메시지로 만들기
    mocker.patch(
        "app.slack.events.log._is_thread_message", new=AsyncMock(return_value=False)
    )

    # 오늘 시점 ts (3일 이내)
    recent_ts = str(datetime.now().timestamp())

    point_service = MagicMock()
    point_service.grant_if_notice_emoji_checked.return_value = "공지 포인트 지급!"
    mocker.patch(
        "app.slack.events.log.PointService", return_value=point_service
    )
    mocker.patch(
        "app.slack.events.log.SlackRepository", return_value=MagicMock()
    )
    mocker.patch(
        "app.slack.events.log.send_point_noti_message", new=AsyncMock()
    )

    body = make_reaction_body(
        user_id="U_REACT",
        channel_id=settings.NOTICE_CHANNEL,
        item_ts=recent_ts,
        reaction="noti-check",
        event_ts=recent_ts,
    )

    await log_events.handle_reaction_added(
        ack=ack, body=body, client=fake_slack_client
    )

    point_service.grant_if_notice_emoji_checked.assert_called_once_with(user_id="U_REACT")
    # 기록이 저장되었는지 (CSV 파일이 생성됨)
    assert (tmp_store / "_checked_notice.csv").exists()


@pytest.mark.asyncio
async def test_handle_reaction_added_notice_skipped_when_thread_message(
    ack, fake_slack_client, mocker
) -> None:
    """⚠️ 공지 채널 + noti-check 인데 스레드 메시지 → 포인트 지급 X."""
    mocker.patch(
        "app.slack.events.log.bigquery_queue.emojis_upload_queue", new=[]
    )
    # _is_thread_message 가 True 를 반환하도록
    mocker.patch(
        "app.slack.events.log._is_thread_message", new=AsyncMock(return_value=True)
    )
    point_service = MagicMock()
    mocker.patch(
        "app.slack.events.log.PointService", return_value=point_service
    )

    body = make_reaction_body(
        channel_id=settings.NOTICE_CHANNEL,
        reaction="noti-check",
    )

    await log_events.handle_reaction_added(
        ack=ack, body=body, client=fake_slack_client
    )

    point_service.grant_if_notice_emoji_checked.assert_not_called()


@pytest.mark.asyncio
async def test_handle_reaction_added_notice_skipped_when_already_checked(
    ack, fake_slack_client, mocker
) -> None:
    """⚠️ 이미 확인한 기록이 있다면 → 포인트 지급 X."""
    mocker.patch(
        "app.slack.events.log.bigquery_queue.emojis_upload_queue", new=[]
    )
    mocker.patch(
        "app.slack.events.log._is_thread_message", new=AsyncMock(return_value=False)
    )
    mocker.patch("app.slack.events.log._is_checked_notice", return_value=True)
    point_service = MagicMock()
    mocker.patch(
        "app.slack.events.log.PointService", return_value=point_service
    )

    body = make_reaction_body(
        channel_id=settings.NOTICE_CHANNEL,
        reaction="noti-check",
        item_ts=str(datetime.now().timestamp()),
        event_ts=str(datetime.now().timestamp()),
    )

    await log_events.handle_reaction_added(
        ack=ack, body=body, client=fake_slack_client
    )

    point_service.grant_if_notice_emoji_checked.assert_not_called()


@pytest.mark.asyncio
async def test_handle_reaction_added_notice_skipped_when_too_old(
    ack, fake_slack_client, mocker
) -> None:
    """⚠️ 공지가 3일보다 이전이면 → 포인트 지급 X."""
    mocker.patch(
        "app.slack.events.log.bigquery_queue.emojis_upload_queue", new=[]
    )
    mocker.patch(
        "app.slack.events.log._is_thread_message", new=AsyncMock(return_value=False)
    )
    mocker.patch("app.slack.events.log._is_checked_notice", return_value=False)
    point_service = MagicMock()
    mocker.patch(
        "app.slack.events.log.PointService", return_value=point_service
    )

    old_ts = str((datetime.now() - timedelta(days=10)).timestamp())
    body = make_reaction_body(
        channel_id=settings.NOTICE_CHANNEL,
        reaction="noti-check",
        item_ts=old_ts,
        event_ts=old_ts,
    )

    await log_events.handle_reaction_added(
        ack=ack, body=body, client=fake_slack_client
    )

    point_service.grant_if_notice_emoji_checked.assert_not_called()


# ---------------------------------------------------------------------------
# handle_reaction_added — PRIMARY 채널 + catch-kyle (성윤을 잡아라)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_reaction_added_super_admin_post_grants_point(
    ack, fake_slack_client, mocker
) -> None:
    """✅ PRIMARY 채널 + catch-kyle + 1일 이내 + super_admin 글 → 포인트."""
    mocker.patch(
        "app.slack.events.log.bigquery_queue.emojis_upload_queue", new=[]
    )
    mocker.patch(
        "app.slack.events.log._is_checked_super_admin_post", return_value=False
    )
    mocker.patch(
        "app.slack.events.log._write_checked_super_admin_post"
    )
    repo = MagicMock()
    repo.get_content_by.return_value = factories.make_content(
        user_id=settings.SUPER_ADMIN, ts="1700000000.000100"
    )
    mocker.patch(
        "app.slack.events.log.SlackRepository", return_value=repo
    )
    point_service = MagicMock()
    point_service.grant_if_super_admin_post_reacted.return_value = "성윤 포인트!"
    mocker.patch(
        "app.slack.events.log.PointService", return_value=point_service
    )
    mocker.patch(
        "app.slack.events.log.send_point_noti_message", new=AsyncMock()
    )

    recent_ts = str(datetime.now().timestamp())
    body = make_reaction_body(
        user_id="U_REACT",
        item_user=settings.TTOBOT_USER_ID,
        channel_id=PRIMARY_CHANNEL[0],
        item_ts=recent_ts,
        event_ts=recent_ts,
        reaction="catch-kyle",
    )

    await log_events.handle_reaction_added(
        ack=ack, body=body, client=fake_slack_client
    )

    point_service.grant_if_super_admin_post_reacted.assert_called_once_with(
        user_id="U_REACT"
    )


@pytest.mark.asyncio
async def test_handle_reaction_added_super_admin_skipped_when_old(
    ack, fake_slack_client, mocker
) -> None:
    """⚠️ 1일 보다 이전 → 포인트 지급 X."""
    mocker.patch(
        "app.slack.events.log.bigquery_queue.emojis_upload_queue", new=[]
    )
    mocker.patch(
        "app.slack.events.log._is_checked_super_admin_post", return_value=False
    )
    point_service = MagicMock()
    mocker.patch(
        "app.slack.events.log.PointService", return_value=point_service
    )

    old_ts = str((datetime.now() - timedelta(days=2)).timestamp())
    body = make_reaction_body(
        item_user=settings.TTOBOT_USER_ID,
        channel_id=PRIMARY_CHANNEL[0],
        item_ts=old_ts,
        event_ts=old_ts,
        reaction="catch-kyle",
    )

    await log_events.handle_reaction_added(
        ack=ack, body=body, client=fake_slack_client
    )

    point_service.grant_if_super_admin_post_reacted.assert_not_called()


@pytest.mark.asyncio
async def test_handle_reaction_added_super_admin_skipped_when_not_super_admin_post(
    ack, fake_slack_client, mocker
) -> None:
    """⚠️ 글 작성자가 super_admin 이 아니면 → 포인트 지급 X."""
    mocker.patch(
        "app.slack.events.log.bigquery_queue.emojis_upload_queue", new=[]
    )
    mocker.patch(
        "app.slack.events.log._is_checked_super_admin_post", return_value=False
    )
    repo = MagicMock()
    repo.get_content_by.return_value = factories.make_content(
        user_id="U_NOT_SUPER", ts="1.0"
    )
    mocker.patch(
        "app.slack.events.log.SlackRepository", return_value=repo
    )
    point_service = MagicMock()
    mocker.patch(
        "app.slack.events.log.PointService", return_value=point_service
    )

    recent_ts = str(datetime.now().timestamp())
    body = make_reaction_body(
        item_user=settings.TTOBOT_USER_ID,
        channel_id=PRIMARY_CHANNEL[0],
        item_ts=recent_ts,
        event_ts=recent_ts,
        reaction="catch-kyle",
    )

    await log_events.handle_reaction_added(
        ack=ack, body=body, client=fake_slack_client
    )

    point_service.grant_if_super_admin_post_reacted.assert_not_called()


@pytest.mark.asyncio
async def test_handle_reaction_added_super_admin_skipped_when_already_checked(
    ack, fake_slack_client, mocker
) -> None:
    """⚠️ 이미 확인한 기록 → 포인트 지급 X."""
    mocker.patch(
        "app.slack.events.log.bigquery_queue.emojis_upload_queue", new=[]
    )
    mocker.patch(
        "app.slack.events.log._is_checked_super_admin_post", return_value=True
    )
    point_service = MagicMock()
    mocker.patch(
        "app.slack.events.log.PointService", return_value=point_service
    )

    recent_ts = str(datetime.now().timestamp())
    body = make_reaction_body(
        item_user=settings.TTOBOT_USER_ID,
        channel_id=PRIMARY_CHANNEL[0],
        item_ts=recent_ts,
        event_ts=recent_ts,
        reaction="catch-kyle",
    )

    await log_events.handle_reaction_added(
        ack=ack, body=body, client=fake_slack_client
    )

    point_service.grant_if_super_admin_post_reacted.assert_not_called()


# ---------------------------------------------------------------------------
# handle_reaction_removed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_reaction_removed_only_acks(ack) -> None:
    """✅ reaction_removed 핸들러는 ack 만 호출."""
    body = make_reaction_body()
    await log_events.handle_reaction_removed(ack=ack, body=body)
    ack.assert_awaited_once()


# ---------------------------------------------------------------------------
# _is_thread_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_thread_message_returns_false_when_no_thread_ts(
    fake_slack_client,
) -> None:
    """✅ thread_ts 키가 없으면 False (일반 메시지)."""
    fake_slack_client.conversations_replies.return_value = {
        "messages": [{"ts": "1.0"}]
    }
    # 캐시를 우회하기 위해 매번 다른 ts 사용
    result = await log_events._is_thread_message(
        client=fake_slack_client, channel_id="C_T1", ts="1.0"
    )
    assert result is False


@pytest.mark.asyncio
async def test_is_thread_message_returns_false_when_thread_ts_equals_ts(
    fake_slack_client,
) -> None:
    """✅ thread_ts == ts → 댓글이 있는 일반 메시지 → False."""
    fake_slack_client.conversations_replies.return_value = {
        "messages": [{"ts": "2.0", "thread_ts": "2.0"}]
    }
    result = await log_events._is_thread_message(
        client=fake_slack_client, channel_id="C_T2", ts="2.0"
    )
    assert result is False


@pytest.mark.asyncio
async def test_is_thread_message_returns_true_when_thread_ts_differs(
    fake_slack_client,
) -> None:
    """✅ thread_ts != ts → 스레드 댓글 → True."""
    fake_slack_client.conversations_replies.return_value = {
        "messages": [{"ts": "3.0", "thread_ts": "1.0"}]
    }
    result = await log_events._is_thread_message(
        client=fake_slack_client, channel_id="C_T3", ts="3.0"
    )
    assert result is True


@pytest.mark.asyncio
async def test_is_thread_message_returns_false_when_message_not_found(
    fake_slack_client,
) -> None:
    """🌀 messages 리스트에 대상 ts가 없으면 False."""
    fake_slack_client.conversations_replies.return_value = {"messages": []}
    result = await log_events._is_thread_message(
        client=fake_slack_client, channel_id="C_T4", ts="4.0"
    )
    assert result is False


# ---------------------------------------------------------------------------
# _is_checked_notice / _write_checked_notice
# ---------------------------------------------------------------------------


def test_is_checked_notice_false_when_file_missing(tmp_store) -> None:
    """🌀 파일 자체가 없을 때 False."""
    (tmp_store / "_checked_notice.csv").unlink()
    assert log_events._is_checked_notice("U_X", "ts_1") is False


def test_write_then_check_notice_returns_true(tmp_store) -> None:
    """✅ 신규 기록 → 다음 호출에서 True."""
    # 파일은 헤더만 있는 빈 상태에서 시작
    log_events._write_checked_notice("U_X", "1700000000.000100")
    assert log_events._is_checked_notice("U_X", "1700000000.000100") is True


def test_check_notice_false_for_different_user(tmp_store) -> None:
    """🌀 다른 user_id → False."""
    log_events._write_checked_notice("U_A", "1.0")
    assert log_events._is_checked_notice("U_B", "1.0") is False


# ---------------------------------------------------------------------------
# _is_checked_super_admin_post / _write_checked_super_admin_post
# ---------------------------------------------------------------------------


def test_is_checked_super_admin_post_false_when_file_missing(tmp_store) -> None:
    """🌀 파일이 없을 때 False."""
    (tmp_store / "_checked_super_admin_post.csv").unlink()
    assert log_events._is_checked_super_admin_post("U_X", "ts_1") is False


def test_write_then_check_super_admin_post_returns_true(tmp_store) -> None:
    """✅ 신규 기록 → 다음 호출에서 True."""
    log_events._write_checked_super_admin_post("U_X", "1.0", "C_X")
    assert log_events._is_checked_super_admin_post("U_X", "1.0") is True
