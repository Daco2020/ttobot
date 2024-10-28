import datetime

import pytest

from pytest_mock import MockerFixture
from app.models import Content, User
from app.slack.repositories import SlackRepository
from app.slack.services.point import PointService


@pytest.mark.parametrize(
    "user, point_name, point",
    [
        (
            User(
                user_id="유저아이디",
                name="제출 내역이 없는 영콤보",
                channel_name="채널이름",
                channel_id="채널아이디",
                intro="업데이트 예정입니다.",
                contents=[],
                cohort="10기",
                deposit="100000",
            ),
            None,
            None,
        ),
        (
            User(
                user_id="유저아이디",
                name="전전 회차에 미제출한 일콤보",
                channel_name="채널이름",
                channel_id="채널아이디",
                intro="업데이트 예정입니다.",
                contents=[
                    Content(
                        dt="2024-11-24 15:00:00",
                        user_id="유저아이디",
                        username="유저이름",
                        type="submit",
                        content_url="https://example.com",
                        title="직전 회차 제출 글",
                        category="일상 & 생각",
                        tags="태그1,태그2",
                        curation_flag="N",
                        ts="1730086982.752899",
                    ),
                    Content(
                        dt="2024-10-27 15:00:00",
                        user_id="유저아이디",
                        username="유저이름",
                        type="submit",
                        content_url="https://example.com",
                        title="전전전 회차 제출 글",
                        category="일상 & 생각",
                        tags="태그1,태그2",
                        curation_flag="N",
                        ts="1730086982.752899",
                    ),
                ],
                cohort="10기",
                deposit="100000",
            ),
            "글 제출 콤보",
            "10",
        ),
        (
            User(
                user_id="유저아이디",
                name="이콤보",
                channel_name="채널이름",
                channel_id="채널아이디",
                intro="업데이트 예정입니다.",
                contents=[
                    Content(
                        dt="2024-11-24 15:00:00",
                        user_id="유저아이디",
                        username="유저이름",
                        type="submit",
                        content_url="https://example.com",
                        title="직전 회차 제출 글",
                        category="일상 & 생각",
                        tags="태그1,태그2",
                        curation_flag="N",
                        ts="1730086982.752899",
                    ),
                    Content(
                        dt="2024-11-10 15:00:00",
                        user_id="유저아이디",
                        username="유저아이디",
                        type="submit",
                        content_url="https://example.com",
                        title="직전 회차 제출 글",
                        category="일상 & 생각",
                        tags="태그1,태그2",
                        curation_flag="N",
                        ts="1730086982.752899",
                    ),
                ],
                cohort="10기",
                deposit="100000",
            ),
            "글 제출 콤보",
            "20",
        ),
        (
            User(
                user_id="유저아이디",
                name="중간에 패스가 있는 삼콤보",
                channel_name="채널이름",
                channel_id="채널아이디",
                intro="업데이트 예정입니다.",
                contents=[
                    Content(
                        dt="2024-11-24 15:00:00",
                        user_id="유저아이디",
                        username="유저이름",
                        type="submit",
                        content_url="https://example.com",
                        title="직전 회차 제출 글",
                        category="일상 & 생각",
                        tags="태그1,태그2",
                        curation_flag="N",
                        ts="1730086982.752899",
                    ),
                    Content(
                        dt="2024-11-10 15:00:00",
                        user_id="유저아이디",
                        username="유저아이디",
                        type="submit",
                        content_url="https://example.com",
                        title="전전 회차 제출 글",
                        category="일상 & 생각",
                        tags="태그1,태그2",
                        curation_flag="N",
                        ts="1730086982.752899",
                    ),
                    Content(
                        dt="2024-10-27 15:00:00",
                        user_id="유저아이디",
                        username="유저아이디",
                        type="pass",
                        content_url="",
                        title="전전전 회차 패스 글",
                        category="",
                        tags="",
                        curation_flag="N",
                        ts="1730086982.752899",
                    ),
                    Content(
                        dt="2024-10-13 15:00:00",
                        user_id="유저아이디",
                        username="유저아이디",
                        type="submit",
                        content_url="https://example.com",
                        title="전전전전 회차 제출 글",
                        category="일상 & 생각",
                        tags="태그1,태그2",
                        curation_flag="N",
                        ts="1730086982.752899",
                    ),
                ],
                cohort="10기",
                deposit="100000",
            ),
            "글 제출 3콤보 보너스",
            "300",
        ),
    ],
)
def test_grant_if_post_submitted_continuously(
    user: User,
    point_name: str | None,
    point: str | None,
    point_service: PointService,
    mocker: MockerFixture,
) -> None:
    """
    연속으로 글을 제출한다면 연속 콤보에 따른 보너스 포인트를 지급합니다.
    현재 회차 제출에 대한 연속 콤보 포인트는 지급입니다. (현재 회차는 제출 건은 반영되지 않습니다.)


    - 1콤보(2회 연속 제출) 라면 콤보 포인트는 10점 입니다.
        - 중간에 미제출 했다면 콤보는 다시 시작합니다.
    - 2콤보(3회 연속 제출) 라면 콤보 포인트는 20점 입니다.
    - 3콤보(4회 연속 제출) 라면 콤보 포인트는 300점 입니다.
        - 중간에 패스를 한 경우 콤보는 연장됩니다.
    """
    # given
    mocker.patch(
        "app.models.DUE_DATES",
        [
            datetime.datetime(2024, 9, 29).date(),  # 0회차 (시작일)
            datetime.datetime(2024, 10, 13).date(),  # 1회차
            datetime.datetime(2024, 10, 27).date(),  # 2회차
            datetime.datetime(2024, 11, 10).date(),  # 3회차
            datetime.datetime(2024, 11, 24).date(),  # 4회차
            datetime.datetime(2024, 12, 8).date(),  # 5회차 (현재 회차)
        ],
    )
    mocker.patch(
        "app.models.tz_now",
        return_value=datetime.datetime(2024, 11, 25, 15, 0, 0),
    )
    mocker.patch.object(
        SlackRepository,
        "get_user",
        return_value=user,
    )

    # when
    result = point_service.grant_if_post_submitted_continuously(user_id=user.user_id)

    # then
    if point_name is None:  # 제출 내역이 없는 경우
        assert result is None

    else:
        expected_message = f"<@{user.user_id}>님 `{point_name}`(으)로 `{point}`포인트를 획득했어요! 🎉\n총 포인트와 내역은 또봇 [홈] 탭에서 확인할 수 있어요."
        assert result == expected_message
