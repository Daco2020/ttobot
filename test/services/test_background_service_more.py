"""BackgroundService 추가 테스트.

기존 `test_background_service.py` 의 send_reminder_message_to_user 외에
- send_reminder_message_to_user 의 0명 케이스
- prepare_subscribe_message_data
- send_subscription_messages
- _send_subscription_message
를 다룬다.
"""

from __future__ import annotations

import csv
from datetime import datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from pytest_mock import MockerFixture
from slack_bolt.async_app import AsyncApp

from app.config import settings
from app.slack.repositories import SlackRepository
from app.slack.services.background import BackgroundService
from test import factories
from test.conftest import FakeSlackApp


# ---------------------------------------------------------------------------
# send_reminder_message_to_user — 추가 케이스
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_reminder_message_to_user_zero_targets(
    background_service: BackgroundService,
    slack_app: FakeSlackApp,
    mocker: MockerFixture,
) -> None:
    """🌀 대상 0명 → 관리자 채널에 '0 명' 메시지만 전송."""
    mocker.patch.object(SlackRepository, "fetch_users", return_value=[])
    chat_post_mock = mocker.patch.object(
        slack_app.client, "chat_postMessage", new=AsyncMock()
    )

    await background_service.send_reminder_message_to_user(cast(AsyncApp, slack_app))

    chat_post_mock.assert_awaited_once()
    kwargs = chat_post_mock.await_args.kwargs
    assert kwargs["channel"] == settings.ADMIN_CHANNEL
    assert "총 0 명" in kwargs["text"]


# ---------------------------------------------------------------------------
# prepare_subscribe_message_data
# ---------------------------------------------------------------------------


def _write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


@pytest.mark.asyncio
async def test_prepare_subscribe_message_filters_yesterday_submits(
    tmp_store, mocker: MockerFixture
) -> None:
    """✅ 어제 작성된 submit 글만 필터링하여 임시 CSV 에 저장."""
    today = datetime(2025, 6, 15, 12, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    yesterday = "2025-06-14"
    two_days_ago = "2025-06-13"

    mocker.patch("app.slack.services.background.tz_now", return_value=today)

    repo = MagicMock()
    repo.fetch_subscriptions.return_value = [
        factories.make_subscription(
            user_id="U_SUB1", target_user_id="U_AUTHOR", target_user_channel="C_AUTHOR"
        ),
        factories.make_subscription(
            user_id="U_SUB2", target_user_id="U_AUTHOR", target_user_channel="C_AUTHOR"
        ),
    ]
    repo.fetch_subscriptions_by_target_user_id.return_value = (
        repo.fetch_subscriptions.return_value
    )

    # contents.csv 작성
    _write_csv(
        tmp_store / "contents.csv",
        [
            "user_id",
            "username",
            "title",
            "content_url",
            "dt",
            "category",
            "description",
            "type",
            "tags",
            "curation_flag",
            "ts",
            "feedback_intensity",
        ],
        [
            {  # 어제 + submit (포함)
                "user_id": "U_AUTHOR",
                "username": "작성자",
                "title": "어제의 글",
                "content_url": "https://e.com/y",
                "dt": f"{yesterday} 21:00:00",
                "category": "기술 & 언어",
                "description": "",
                "type": "submit",
                "tags": "",
                "curation_flag": "N",
                "ts": "1.0",
                "feedback_intensity": "HOT",
            },
            {  # 그저께 + submit (제외)
                "user_id": "U_AUTHOR",
                "username": "작성자",
                "title": "그저께",
                "content_url": "https://e.com/2",
                "dt": f"{two_days_ago} 21:00:00",
                "category": "",
                "description": "",
                "type": "submit",
                "tags": "",
                "curation_flag": "N",
                "ts": "2.0",
                "feedback_intensity": "HOT",
            },
            {  # 어제 + pass (제외)
                "user_id": "U_AUTHOR",
                "username": "작성자",
                "title": "패스",
                "content_url": "",
                "dt": f"{yesterday} 09:00:00",
                "category": "",
                "description": "",
                "type": "pass",
                "tags": "",
                "curation_flag": "N",
                "ts": "3.0",
                "feedback_intensity": "HOT",
            },
        ],
    )

    bg = BackgroundService(repo=repo)
    await bg.prepare_subscribe_message_data()

    output_path = tmp_store / "_subscription_messages.csv"
    assert output_path.exists()
    df = pd.read_csv(output_path)
    # 두 명의 구독자 × 어제 글 1개 = 2 행
    assert len(df) == 2
    assert set(df["user_id"]) == {"U_SUB1", "U_SUB2"}
    assert all(df["title"] == "어제의 글")


@pytest.mark.asyncio
async def test_prepare_subscribe_message_creates_no_csv_when_no_match(
    tmp_store, mocker: MockerFixture
) -> None:
    """🌀 어제 글이 없으면 임시 CSV 가 생성되지 않는다."""
    today = datetime(2025, 6, 15, 12, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    mocker.patch("app.slack.services.background.tz_now", return_value=today)

    repo = MagicMock()
    repo.fetch_subscriptions.return_value = [
        factories.make_subscription(
            user_id="U_SUB", target_user_id="U_AUTHOR", target_user_channel="C_AUTHOR"
        )
    ]
    repo.fetch_subscriptions_by_target_user_id.return_value = (
        repo.fetch_subscriptions.return_value
    )

    _write_csv(
        tmp_store / "contents.csv",
        [
            "user_id",
            "username",
            "title",
            "content_url",
            "dt",
            "category",
            "description",
            "type",
            "tags",
            "curation_flag",
            "ts",
            "feedback_intensity",
        ],
        [
            {  # 옛날 글
                "user_id": "U_AUTHOR",
                "username": "작성자",
                "title": "오래된 글",
                "content_url": "https://e.com/o",
                "dt": "2025-05-01 09:00:00",
                "category": "",
                "description": "",
                "type": "submit",
                "tags": "",
                "curation_flag": "N",
                "ts": "1.0",
                "feedback_intensity": "HOT",
            }
        ],
    )

    bg = BackgroundService(repo=repo)
    await bg.prepare_subscribe_message_data()

    assert not (tmp_store / "_subscription_messages.csv").exists()


@pytest.mark.asyncio
async def test_prepare_subscribe_message_uses_writing_channel_for_writing_user(
    tmp_store, mocker: MockerFixture
) -> None:
    """✅ 글쓰기 참여 신청한 작성자의 글 → target_user_channel 을 WRITING_CHANNEL 로 치환."""
    today = datetime(2025, 6, 15, 12, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    yesterday = "2025-06-14"
    mocker.patch("app.slack.services.background.tz_now", return_value=today)

    repo = MagicMock()
    repo.fetch_subscriptions.return_value = [
        factories.make_subscription(
            user_id="U_SUB", target_user_id="U_WRITER", target_user_channel="C_OLD"
        )
    ]
    repo.fetch_subscriptions_by_target_user_id.return_value = (
        repo.fetch_subscriptions.return_value
    )

    _write_csv(
        tmp_store / "contents.csv",
        [
            "user_id",
            "username",
            "title",
            "content_url",
            "dt",
            "category",
            "description",
            "type",
            "tags",
            "curation_flag",
            "ts",
            "feedback_intensity",
        ],
        [
            {
                "user_id": "U_WRITER",
                "username": "작성자",
                "title": "어제의 글",
                "content_url": "https://e.com/w",
                "dt": f"{yesterday} 09:00:00",
                "category": "",
                "description": "",
                "type": "submit",
                "tags": "",
                "curation_flag": "N",
                "ts": "1.0",
                "feedback_intensity": "HOT",
            }
        ],
    )

    # writing_participation.csv 에 등록된 유저
    _write_csv(
        tmp_store / "writing_participation.csv",
        ["user_id", "name", "created_at", "is_writing_participation"],
        [
            {
                "user_id": "U_WRITER",
                "name": "작성자",
                "created_at": "2025-01-01 09:00:00",
                "is_writing_participation": "True",
            }
        ],
    )

    bg = BackgroundService(repo=repo)
    await bg.prepare_subscribe_message_data()

    df = pd.read_csv(tmp_store / "_subscription_messages.csv")
    assert df["target_user_channel"].iloc[0] == settings.WRITING_CHANNEL


@pytest.mark.asyncio
async def test_prepare_subscribe_message_removes_existing_temp_csv(
    tmp_store, mocker: MockerFixture
) -> None:
    """🌀 기존 임시 CSV 가 있으면 삭제 후 진행."""
    today = datetime(2025, 6, 15, 12, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    mocker.patch("app.slack.services.background.tz_now", return_value=today)

    # 기존 임시 파일 생성
    pre_existing = tmp_store / "_subscription_messages.csv"
    pre_existing.write_text(
        "user_id,target_user_id,target_user_channel,ts,title,dt\nOLD,X,C,1,t,2025-01-01\n"
    )

    repo = MagicMock()
    repo.fetch_subscriptions.return_value = []  # 신규 데이터 없음

    _write_csv(
        tmp_store / "contents.csv",
        [
            "user_id",
            "username",
            "title",
            "content_url",
            "dt",
            "category",
            "description",
            "type",
            "tags",
            "curation_flag",
            "ts",
            "feedback_intensity",
        ],
        [],
    )

    bg = BackgroundService(repo=repo)
    await bg.prepare_subscribe_message_data()

    # 기존 파일은 삭제되어야 하고, 매칭 없으니 새 파일도 생성되지 않아야 한다.
    assert not pre_existing.exists()


# ---------------------------------------------------------------------------
# send_subscription_messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_subscription_messages_no_csv_returns_silently(
    tmp_store, slack_app: FakeSlackApp, mocker: MockerFixture
) -> None:
    """🌀 임시 CSV 가 없으면 그냥 종료 (관리자 알림도 없음)."""
    chat_post_mock = mocker.patch.object(
        slack_app.client, "chat_postMessage", new=AsyncMock()
    )

    bg = BackgroundService(repo=MagicMock())
    await bg.send_subscription_messages(cast(AsyncApp, slack_app))

    chat_post_mock.assert_not_called()


@pytest.mark.asyncio
async def test_send_subscription_messages_sends_each_row(
    tmp_store, slack_app: FakeSlackApp, mocker: MockerFixture
) -> None:
    """✅ CSV 행마다 _send_subscription_message 호출 + 마지막에 요약 메시지."""
    chat_post_mock = mocker.patch.object(
        slack_app.client, "chat_postMessage", new=AsyncMock()
    )

    # _send_subscription_message 자체는 mock 으로 대체 (permalink 호출 회피)
    send_one_mock = mocker.patch.object(
        BackgroundService, "_send_subscription_message", new=AsyncMock()
    )

    pd.DataFrame(
        [
            {
                "user_id": "U_SUB1",
                "target_user_id": "U_A",
                "target_user_channel": "C_A",
                "ts": "1.0",
                "title": "글1",
                "dt": "2025-06-14",
            },
            {
                "user_id": "U_SUB2",
                "target_user_id": "U_A",
                "target_user_channel": "C_A",
                "ts": "1.0",
                "title": "글1",
                "dt": "2025-06-14",
            },
        ]
    ).to_csv(
        tmp_store / "_subscription_messages.csv", index=False, quoting=csv.QUOTE_ALL
    )

    bg = BackgroundService(repo=MagicMock())
    await bg.send_subscription_messages(cast(AsyncApp, slack_app))

    assert send_one_mock.await_count == 2
    chat_post_mock.assert_awaited_once()
    summary = chat_post_mock.await_args.kwargs["text"]
    assert "총 2 명에게" in summary
    assert "2 개의" in summary


@pytest.mark.asyncio
async def test_send_subscription_messages_swallows_individual_failures(
    tmp_store, slack_app: FakeSlackApp, mocker: MockerFixture
) -> None:
    """⚠️ 개별 발송 실패 → 관리자 채널 알림 + 다음 행 계속."""
    chat_post_mock = mocker.patch.object(
        slack_app.client, "chat_postMessage", new=AsyncMock()
    )

    send_one_mock = mocker.patch.object(
        BackgroundService,
        "_send_subscription_message",
        new=AsyncMock(side_effect=[RuntimeError("permalink 실패"), None]),
    )

    pd.DataFrame(
        [
            {
                "user_id": "U_FAIL",
                "target_user_id": "U_A",
                "target_user_channel": "C_A",
                "ts": "1.0",
                "title": "글1",
                "dt": "2025-06-14",
            },
            {
                "user_id": "U_OK",
                "target_user_id": "U_A",
                "target_user_channel": "C_A",
                "ts": "1.0",
                "title": "글1",
                "dt": "2025-06-14",
            },
        ]
    ).to_csv(
        tmp_store / "_subscription_messages.csv", index=False, quoting=csv.QUOTE_ALL
    )

    bg = BackgroundService(repo=MagicMock())
    await bg.send_subscription_messages(cast(AsyncApp, slack_app))

    # 두 행 모두 시도되어야 함
    assert send_one_mock.await_count == 2
    # 관리자 알림: 실패 1번 + 마지막 요약 1번
    posted_texts = [c.kwargs["text"] for c in chat_post_mock.await_args_list]
    assert any("U_FAIL" in t and "permalink 실패" in t for t in posted_texts)
    assert any("총" in t and "명에게" in t for t in posted_texts)


# ---------------------------------------------------------------------------
# _send_subscription_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_subscription_message_posts_with_permalink(
    slack_app: FakeSlackApp, mocker: MockerFixture
) -> None:
    """✅ permalink 가져오기 → 블록 구성 → chat_postMessage 호출."""
    mocker.patch("app.slack.services.background.asyncio.sleep", new=AsyncMock())
    mocker.patch.object(
        slack_app.client,
        "chat_getPermalink",
        new=AsyncMock(return_value={"permalink": "https://slack.example/permalink"}),
    )
    chat_post_mock = mocker.patch.object(
        slack_app.client, "chat_postMessage", new=AsyncMock()
    )

    message = {
        "user_id": "U_SUB",
        "target_user_id": "U_AUTHOR",
        "target_user_channel": "C_AUTHOR",
        "ts": "1700000000.000100",
        "title": "어제의 글",
        "dt": "2025-06-14",
    }

    bg = BackgroundService(repo=MagicMock())
    await bg._send_subscription_message(cast(AsyncApp, slack_app), message)

    chat_post_mock.assert_awaited_once()
    kwargs = chat_post_mock.await_args.kwargs
    assert kwargs["channel"] == "U_SUB"
    assert "<@U_AUTHOR>" in kwargs["text"]


@pytest.mark.asyncio
async def test_send_subscription_message_retries_then_fails(
    slack_app: FakeSlackApp, mocker: MockerFixture
) -> None:
    """⚠️ chat_getPermalink 가 계속 실패 → tenacity 가 3회 재시도 후 예외 전파."""
    mocker.patch("app.slack.services.background.asyncio.sleep", new=AsyncMock())
    permalink_mock = mocker.patch.object(
        slack_app.client,
        "chat_getPermalink",
        new=AsyncMock(side_effect=RuntimeError("network")),
    )

    message = {
        "user_id": "U_SUB",
        "target_user_id": "U_AUTHOR",
        "target_user_channel": "C_AUTHOR",
        "ts": "1.0",
        "title": "글",
        "dt": "2025-06-14",
    }

    bg = BackgroundService(repo=MagicMock())
    with pytest.raises(RuntimeError, match="network"):
        await bg._send_subscription_message(cast(AsyncApp, slack_app), message)

    # tenacity stop_after_attempt(3) → 3회 호출
    assert permalink_mock.await_count == 3
