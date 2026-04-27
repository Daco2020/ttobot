"""슬랙 핸들러 테스트 인프라 스모크 테스트.

핸들러 함수를 직접 호출할 때 ack/say/client/user/service가 잘 주입되는지 확인.
"""

import pytest

from app.slack.events import core as core_events
from test.slack.conftest import make_command_body


@pytest.mark.asyncio
async def test_handle_app_mention_only_calls_ack(ack, say, fake_slack_client) -> None:
    """app_mention 핸들러는 ack 만 호출하고 별도 부수효과가 없어야 한다."""
    # given
    body = {"event": {"type": "app_mention"}}

    # when
    await core_events.handle_app_mention(
        ack=ack, body=body, say=say, client=fake_slack_client
    )

    # then
    ack.assert_awaited_once()
    fake_slack_client.chat_postMessage.assert_not_called()


@pytest.mark.asyncio
async def test_open_help_view_opens_modal(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """/도움말 명령어는 views_open을 한 번 호출해 도움말 모달을 띄운다."""
    # given
    user = factory.make_user(user_id="U_HELP")
    body = make_command_body(user_id=user.user_id, command="/도움말")

    # when
    await core_events.open_help_view(
        ack=ack,
        body=body,
        say=say,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )

    # then
    ack.assert_awaited_once()
    fake_slack_client.views_open.assert_awaited_once()
    kwargs = fake_slack_client.views_open.await_args.kwargs
    assert kwargs["trigger_id"] == body["trigger_id"]
    view = kwargs["view"]
    # 슬랙 SDK의 View.title은 PlainTextObject 객체. 직렬화 후 검증한다.
    assert view.to_dict()["title"]["text"] == "또봇 도움말"
