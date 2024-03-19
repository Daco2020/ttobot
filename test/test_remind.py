from datetime import timedelta
from app.models import Content, User
from app.slack.services import SlackRemindService
from app.utils import tz_now


def test_generate_remind_messages(slack_remind_service: SlackRemindService) -> None:
    """
    정상적으로 리마인드 메시지를 생성하는지 확인합니다.
    - 현재 회차를 제출하지 않은 인원에게 리마인드 메시지를 생성해야합니다.
    - 현재 기수에 해당하는 인원에게 리마인드 메시지를 생성해야합니다.
    """
    # given
    [
        User(
            user_id="리마인드 비대상1",
            name="슬랙봇",
            channel_name="test_channel",
            channel_id="test_channel_id",
            intro="-",  # bot
            contents=[],
        ),
        User(
            user_id="리마인드 대상1",
            name="변덕순",
            channel_name="test_channel",
            channel_id="test_channel_id",
            intro="안녕하세요. 덕순입니다.",
            contents=[],
        ),
        User(
            user_id="리마인드 비대상2",
            name="장득현",
            channel_name="test_channel",
            channel_id="test_channel_id",
            intro="8기 참여자",
            contents=[],
        ),
        User(
            user_id="리마인드 비대상3",
            name="배성진",
            channel_name="test_channel",
            channel_id="test_channel_id",
            intro="안녕하세요. 배성진입니다.",
            contents=[
                Content(
                    dt=(tz_now() - timedelta(days=15)).strftime("%Y-%m-%d %H:%M:%S"),
                    user_id="리마인드 비대상3",
                    username="배성진",
                    type="submit",
                ),
                Content(
                    dt=(tz_now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
                    user_id="리마인드 비대상3",
                    username="배성진",
                    type="submit",
                ),
            ],
        ),
        User(
            user_id="리마인드 대상2",
            name="성연찬",
            channel_name="test_channel",
            channel_id="test_channel_id",
            intro="안녕하세요. 성연찬입니다.",
            contents=[
                Content(
                    dt=(tz_now() - timedelta(days=15)).strftime("%Y-%m-%d %H:%M:%S"),
                    user_id="리마인드 대상2",
                    username="성연찬",
                    type="submit",
                ),
            ],
        ),
    ]

    # when, then
    # TODO: slack_app mock 으로 호출하는지 확인 필요
