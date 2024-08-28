from datetime import timedelta
from typing import cast

from slack_bolt.async_app import AsyncApp

import pytest
from pytest_mock import MockerFixture
from app.models import Content, User
from app.slack.repositories import SlackRepository
from app.slack.services import BackgroundService
from app.utils import tz_now
from test.conftest import FakeSlackApp


@pytest.mark.asyncio
async def test_send_reminder_message_to_user(
    background_service: BackgroundService,
    slack_app: FakeSlackApp,
    mocker: MockerFixture,
) -> None:
    """
    리마인드 대상 유저에게 메시지를 전송하는지 확인합니다.
    - 현재 회차를 제출하지 않은 인원에게 리마인드 메시지를 전송해야 합니다.
    - 현재 기수에 해당하는 인원에게 리마인드 메시지를 전송해야 합니다.
    """
    # given
    mocker.patch(
        "app.models.DUE_DATES",
        [
            tz_now().date() - timedelta(days=14),  # 직전 회차 마감일
            tz_now().date(),  # 현재 회차 마감일
        ],
    )
    mocker.patch.object(
        SlackRepository,
        "fetch_users",
        return_value=[
            User(
                user_id="리마인드 비대상1",
                name="슬랙봇",
                channel_name="슬랙봇",
                channel_id="test_channel_id",
                intro="-",  # bot
                contents=[],
                cohort="9기",
            ),
            User(
                user_id="리마인드 비대상2",
                name="장득현",
                channel_name="test_channel",
                channel_id="test_channel_id",
                intro="",
                contents=[],
                cohort="8기",  # 지난 기수 참여자
            ),
            User(
                user_id="리마인드 비대상3",
                name="배성진",
                channel_name="test_channel",
                channel_id="test_channel_id",
                intro="안녕하세요. 배성진입니다.",
                contents=[
                    Content(  # 이미 제출한 경우
                        dt=(tz_now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
                        user_id="리마인드 비대상3",
                        username="배성진",
                        type="submit",
                    ),
                ],
                cohort="9기",
            ),
            User(
                user_id="리마인드 대상1",
                name="변덕순",
                channel_name="test_channel",
                channel_id="test_channel_id",
                intro="안녕하세요. 덕순입니다.",
                contents=[],  # 제출하지 않은 경우
                cohort="9기",
            ),
            User(
                user_id="리마인드 대상2",
                name="도진홍",
                channel_name="test_channel",
                channel_id="test_channel_id",
                intro="안녕하세요. 도진홍입니다.",
                contents=[
                    Content(  # 지난 회차 제출한 경우
                        dt=(tz_now() - timedelta(days=15)).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        user_id="리마인드 대상2",
                        username="도진홍",
                        type="submit",
                    ),
                ],
                cohort="9기",
            ),
        ],
    )
    slack_client_mock = mocker.patch.object(slack_app.client, "chat_postMessage")

    # when
    await background_service.send_reminder_message_to_user(cast(AsyncApp, slack_app))

    # then
    assert slack_client_mock.call_count == 2
    assert slack_client_mock.call_args_list[0].kwargs["channel"] == "리마인드 대상1"
    assert (
        slack_client_mock.call_args_list[0].kwargs["text"]
        == "오늘은 글또 제출 마감일이에요.\n지난 2주 동안 배우고 경험한 것들을 자정까지 나눠주세요.\n변덕순 님의 이야기를 기다릴게요!🙂"
    )
    assert slack_client_mock.call_args_list[1].kwargs["channel"] == "리마인드 대상2"
    assert (
        slack_client_mock.call_args_list[1].kwargs["text"]
        == "오늘은 글또 제출 마감일이에요.\n지난 2주 동안 배우고 경험한 것들을 자정까지 나눠주세요.\n도진홍 님의 이야기를 기다릴게요!🙂"
    )
