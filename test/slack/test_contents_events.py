"""슬랙 contents 이벤트 핸들러 테스트.

대상: app/slack/events/contents.py
- /제출 (submit_command, submit_view)
- /패스 (pass_command, pass_view)
- /검색 (search_command, submit_search, web_search, back_to_search_view)
- /북마크 (bookmark_command, bookmark_modal, create_bookmark_view,
            bookmark_page_view, handle_bookmark_page, open_overflow_action)
- 자기소개 (open_intro_modal, edit_intro_view, submit_intro_view)
- contents_modal
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.exception import BotException, ClientException
from app.slack.events import contents as contents_events
from app.slack.services.point import UserPoint
from test import factories
from test.slack.conftest import make_action_body, make_command_body, make_view_body


# ---------------------------------------------------------------------------
# /제출 (submit_command)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_command_in_writing_channel_opens_submit_modal(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock, mocker
) -> None:
    """✅ 글쓰기 채널에서 호출 → 제출 모달 open."""
    user = factory.make_user(user_id="U_X")
    # writing_channel_id 가 호출 채널과 같도록 is_writing_participation 을 True 로 만든다
    mocker.patch.object(
        type(user), "is_writing_participation", new_callable=mocker.PropertyMock
    ).return_value = True
    body = make_command_body(user_id="U_X", channel_id=settings.WRITING_CHANNEL)

    await contents_events.submit_command(
        ack=ack,
        body=body,
        say=say,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )

    fake_slack_client.views_open.assert_awaited_once()
    view = fake_slack_client.views_open.await_args.kwargs["view"]
    assert view.callback_id == "submit_view"


@pytest.mark.asyncio
async def test_submit_command_outside_writing_channel_opens_participation(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock, mocker
) -> None:
    """⚠️ 글쓰기 채널이 아닌 곳 → 글쓰기 참여 신청 모달."""
    user = factory.make_user(user_id="U_X", channel_id="C_OTHER")
    mocker.patch.object(
        type(user), "is_writing_participation", new_callable=mocker.PropertyMock
    ).return_value = False
    body = make_command_body(user_id="U_X", channel_id="C_RANDOM")

    await contents_events.submit_command(
        ack=ack,
        body=body,
        say=say,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )

    fake_slack_client.views_open.assert_awaited_once()
    view = fake_slack_client.views_open.await_args.kwargs["view"]
    assert view.callback_id == "writing_participation_view"


# ---------------------------------------------------------------------------
# submit_view (글 제출 완료)
# ---------------------------------------------------------------------------


def _submit_view_state(
    *,
    url: str = "https://example.com/post",
    category: str = "기술 & 언어",
    curation: str = "N",
    feedback_intensity: str = "HOT",
    tag: str = "",
    description: str = "",
    title: str = "",
) -> dict:
    return {
        "content_url": {"url_text_input-action": {"value": url}},
        "category": {"category_select": {"selected_option": {"value": category}}},
        "curation": {"curation_select": {"selected_option": {"value": curation}}},
        "feedback_intensity": {
            "feedback_intensity_select": {"selected_option": {"value": feedback_intensity}}
        },
        "tag": {"tags_input": {"value": tag or None}},
        "description": {"text_input": {"value": description or None}},
        "manual_title_input": {"title_input": {"value": title or None}},
    }


@pytest.mark.asyncio
async def test_submit_view_invalid_url_returns_ack_errors(
    ack, say, fake_slack_client, factory, mocker
) -> None:
    """⚠️ url 검증 실패 → ack(errors=...) 후 예외 raise."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()
    service.validate_url.side_effect = ValueError("링크는 url 형식이어야 해요.")
    point_service = MagicMock()

    body = make_view_body(
        user_id="U_X",
        callback_id="submit_view",
        private_metadata="C_WRITING",
        state_values=_submit_view_state(url="bad"),
    )

    with pytest.raises(ValueError):
        await contents_events.submit_view(
            ack=ack,
            body=body,
            client=fake_slack_client,
            view=body["view"],
            say=say,
            user=user,
            service=service,
            point_service=point_service,
        )

    ack.assert_awaited_once()
    kwargs = ack.await_args.kwargs
    assert kwargs["response_action"] == "errors"
    assert "content_url" in kwargs["errors"]


@pytest.mark.asyncio
async def test_submit_view_get_title_client_exception_propagates(
    ack, say, fake_slack_client, factory, mocker
) -> None:
    """⚠️ get_title 에서 ClientException → ack errors + raise."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()
    service.validate_url.return_value = None
    service.get_title = AsyncMock(side_effect=ClientException("404"))
    point_service = MagicMock()

    body = make_view_body(
        user_id="U_X",
        callback_id="submit_view",
        private_metadata="C_WRITING",
        state_values=_submit_view_state(),
    )

    with pytest.raises(ClientException):
        await contents_events.submit_view(
            ack=ack,
            body=body,
            client=fake_slack_client,
            view=body["view"],
            say=say,
            user=user,
            service=service,
            point_service=point_service,
        )
    kwargs = ack.await_args.kwargs
    assert kwargs["response_action"] == "errors"


@pytest.mark.asyncio
async def test_submit_view_success_grants_points_and_posts(
    ack, say, fake_slack_client, factory, mocker
) -> None:
    """✅ 정상 url + 메타 → 콘텐츠 생성 + 채널 메시지 + 포인트 알림."""
    user = factory.make_user(user_id="U_X", channel_name="1_백엔드", contents=[])
    # is_submit 은 contents 가 비어있으면 False
    service = MagicMock()
    service.validate_url.return_value = None
    service.get_title = AsyncMock(return_value="테스트 글")
    created = factories.make_content(user_id="U_X", curation_flag="N")
    service.create_submit_content = AsyncMock(return_value=created)
    service.update_user_content = AsyncMock(return_value=None)
    service.get_chat_message.return_value = "제출 메시지"

    point_service = MagicMock()
    point_service.grant_if_post_submitted.return_value = ("기본 포인트 지급", False)
    point_service.grant_if_post_submitted_continuously.return_value = None
    point_service.grant_if_post_submitted_to_core_channel_ranking.return_value = None

    fake_slack_client.chat_postMessage.return_value = {"ts": "msg_ts_1"}

    mocker.patch(
        "app.slack.events.contents.send_point_noti_message", new=AsyncMock()
    )
    # 글쓰기 채널로 제출하면 활동 안내 분기를 타지 않아 asyncio.sleep 호출 없음
    body = make_view_body(
        user_id="U_X",
        callback_id="submit_view",
        private_metadata=settings.WRITING_CHANNEL,
        state_values=_submit_view_state(),
    )

    await contents_events.submit_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        view=body["view"],
        say=say,
        user=user,
        service=service,
        point_service=point_service,
    )

    # 첫 번째 ack 호출(인자 없음) 후 chat_postMessage + create_submit_content + update_user_content
    service.create_submit_content.assert_awaited_once()
    service.update_user_content.assert_awaited_once()
    fake_slack_client.chat_postMessage.assert_awaited()
    point_service.grant_if_post_submitted.assert_called_once_with(
        user_id="U_X", is_submit=user.is_submit
    )
    # is_additional 이 False 이므로 콤보/랭킹 분기는 호출되어야 한다
    point_service.grant_if_post_submitted_continuously.assert_called_once()
    point_service.grant_if_post_submitted_to_core_channel_ranking.assert_called_once()
    # curation_flag = N 이므로 grant_if_curation_requested 는 호출되지 않아야 한다
    point_service.grant_if_curation_requested.assert_not_called()


# ---------------------------------------------------------------------------
# /패스 (pass_command, pass_view)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pass_command_opens_modal(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock, mocker
) -> None:
    """✅ pass 가능 상태 → 패스 모달 open."""
    user = factory.make_user(user_id="U_X", contents=[])
    mocker.patch(
        "app.models.DUE_DATES",
        [datetime.date(2025, 1, 1), datetime.date(2025, 12, 31)],
    )
    mocker.patch(
        "app.models.tz_now",
        return_value=datetime.datetime(2025, 6, 15, 12, 0, 0),
    )

    await contents_events.pass_command(
        ack=ack,
        body=make_command_body(user_id="U_X"),
        say=say,
        client=fake_slack_client,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )

    fake_slack_client.views_open.assert_awaited()
    # 마지막 view_open 호출이 pass_view callback 이어야 한다
    last_view = fake_slack_client.views_open.await_args.kwargs["view"]
    assert last_view.callback_id == "pass_view"


@pytest.mark.asyncio
async def test_pass_command_when_pass_count_exceeded(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock, mocker
) -> None:
    """⚠️ pass 횟수 한도 초과 → BotException."""
    user = factory.make_user(
        user_id="U_X",
        contents=[
            factories.make_content(type="pass", dt="2025-01-05 10:00:00"),
            factories.make_content(type="pass", dt="2025-02-05 10:00:00"),
        ],
    )
    mocker.patch(
        "app.models.DUE_DATES",
        [datetime.date(2025, 1, 1), datetime.date(2025, 12, 31)],
    )
    mocker.patch(
        "app.models.tz_now",
        return_value=datetime.datetime(2025, 6, 15, 12, 0, 0),
    )

    with pytest.raises(BotException):
        await contents_events.pass_command(
            ack=ack,
            body=make_command_body(user_id="U_X"),
            say=say,
            client=fake_slack_client,
            user=user,
            service=slack_service,
            point_service=point_service_mock,
        )


@pytest.mark.asyncio
async def test_pass_view_creates_content_and_posts(
    ack, say, fake_slack_client, factory, point_service_mock
) -> None:
    """✅ 정상 패스 → create_pass_content + chat_postMessage + update."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()
    pass_content = factories.make_content(user_id="U_X", type="pass")
    service.create_pass_content = AsyncMock(return_value=pass_content)
    service.update_user_content = AsyncMock(return_value=None)
    service.get_chat_message.return_value = "패스 메시지"

    fake_slack_client.chat_postMessage.return_value = {"ts": "msg_ts"}

    body = make_view_body(
        user_id="U_X",
        callback_id="pass_view",
        private_metadata="C_WRITING",
    )

    await contents_events.pass_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        view=body["view"],
        say=say,
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    service.create_pass_content.assert_awaited_once()
    service.update_user_content.assert_awaited_once()
    fake_slack_client.chat_postMessage.assert_awaited_once()


# ---------------------------------------------------------------------------
# /검색
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_command_opens_search_modal(
    ack, fake_slack_client, slack_service, point_service_mock
) -> None:
    """✅ /검색 → 검색 모달 open."""
    await contents_events.search_command(
        ack=ack,
        body=make_command_body(),
        say=AsyncMock(),
        client=fake_slack_client,
        service=slack_service,
        point_service=point_service_mock,
    )
    fake_slack_client.views_open.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_search_returns_results(
    ack, fake_slack_client, point_service_mock, factory
) -> None:
    """✅ 키워드/이름/카테고리로 검색 → ack(response_action=update, view=...)."""
    service = MagicMock()
    service.fetch_contents.return_value = [
        factories.make_content(title="Python 글", content_url="https://e.com/a"),
        factories.make_content(title="FastAPI 글", content_url="https://e.com/b"),
    ]

    body = make_view_body(
        callback_id="submit_search",
        state_values={
            "keyword_search": {"keyword": {"value": "python"}},
            "author_search": {"author_name": {"value": ""}},
            "category_search": {
                "chosen_category": {"selected_option": {"value": "전체"}}
            },
        },
    )

    await contents_events.submit_search(
        ack=ack,
        body=body,
        client=fake_slack_client,
        service=service,
        point_service=point_service_mock,
    )

    ack.assert_awaited_once()
    kwargs = ack.await_args.kwargs
    assert kwargs["response_action"] == "update"
    title = kwargs["view"].to_dict()["title"]["text"]
    assert "총 2 개의 글" in title


@pytest.mark.asyncio
async def test_submit_search_with_no_results(
    ack, fake_slack_client, point_service_mock
) -> None:
    """🌀 결과 0건 → 'X 개의 글' 텍스트가 0 으로 채워진다."""
    service = MagicMock()
    service.fetch_contents.return_value = []

    body = make_view_body(
        callback_id="submit_search",
        state_values={
            "keyword_search": {"keyword": {"value": "없는키워드"}},
            "author_search": {"author_name": {"value": ""}},
            "category_search": {
                "chosen_category": {"selected_option": {"value": "전체"}}
            },
        },
    )

    await contents_events.submit_search(
        ack=ack,
        body=body,
        client=fake_slack_client,
        service=service,
        point_service=point_service_mock,
    )

    title = ack.await_args.kwargs["view"].to_dict()["title"]["text"]
    assert "총 0 개의 글" in title


@pytest.mark.asyncio
async def test_web_search_only_acks(
    ack, fake_slack_client, slack_service, point_service_mock
) -> None:
    """✅ 웹 검색은 외부 링크라 ack 만 호출."""
    await contents_events.web_search(
        ack=ack,
        body=make_action_body(),
        client=fake_slack_client,
        service=slack_service,
        point_service=point_service_mock,
    )
    ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_back_to_search_view_returns_to_search_modal(
    ack, fake_slack_client, slack_service, point_service_mock
) -> None:
    """✅ 다시 검색 버튼 → response_type=update + 검색 모달."""
    await contents_events.back_to_search_view(
        ack=ack,
        body=make_view_body(),
        say=AsyncMock(),
        client=fake_slack_client,
        service=slack_service,
        point_service=point_service_mock,
    )
    ack.assert_awaited_once()
    kwargs = ack.await_args.kwargs
    assert kwargs["response_type"] == "update"
    assert kwargs["view"].callback_id == "submit_search"


# ---------------------------------------------------------------------------
# /북마크 (bookmark_command, bookmark_modal, create_bookmark_view)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bookmark_command_with_zero_bookmarks(
    ack, fake_slack_client, factory, point_service_mock
) -> None:
    """🌀 북마크 0건 → 모달 open."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()
    service.fetch_bookmarks.return_value = []
    service.fetch_contents_by_ids.return_value = []

    await contents_events.bookmark_command(
        ack=ack,
        body=make_command_body(user_id="U_X"),
        say=AsyncMock(),
        client=fake_slack_client,
        user=user,
        service=service,
        point_service=point_service_mock,
    )
    fake_slack_client.views_open.assert_awaited_once()


@pytest.mark.asyncio
async def test_bookmark_command_with_multiple_pages_shows_next_button(
    ack, fake_slack_client, factory, point_service_mock
) -> None:
    """✅ 컨텐츠 21개 (페이지 2개) → '다음 페이지' 버튼 노출."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()
    bookmarks = [
        factories.make_bookmark(content_ts=str(i)) for i in range(21)
    ]
    contents = [
        factories.make_content(ts=str(i), content_url=f"https://e.com/{i}")
        for i in range(21)
    ]
    service.fetch_bookmarks.return_value = bookmarks
    service.fetch_contents_by_ids.return_value = contents

    await contents_events.bookmark_command(
        ack=ack,
        body=make_command_body(user_id="U_X"),
        say=AsyncMock(),
        client=fake_slack_client,
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    view = fake_slack_client.views_open.await_args.kwargs["view"]
    button_ids: list[str] = []
    for b in view.to_dict()["blocks"]:
        if b.get("type") == "actions":
            for el in b.get("elements", []):
                if "action_id" in el:
                    button_ids.append(el["action_id"])
    assert "next_bookmark_page_action" in button_ids


@pytest.mark.asyncio
async def test_bookmark_modal_when_already_bookmarked(
    ack, fake_slack_client, factory, point_service_mock
) -> None:
    """⚠️ 이미 북마크된 글 → '이미 북마크한 글이에요.' 모달."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()
    service.get_content_by.return_value = factories.make_content(
        user_id="U_AUTHOR", ts="ts_1"
    )
    service.get_bookmark.return_value = factories.make_bookmark(
        user_id="U_X", content_ts="ts_1"
    )

    body = make_action_body(
        actions=[
            {
                "action_id": "bookmark_modal",
                "type": "button",
                "value": '{"user_id": "U_AUTHOR", "dt": "2025-01-01 10:00:00"}',
            }
        ]
    )

    await contents_events.bookmark_modal(
        ack=ack,
        body=body,
        client=fake_slack_client,
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    fake_slack_client.views_open.assert_awaited_once()
    view = fake_slack_client.views_open.await_args.kwargs["view"]
    body_text = "".join(
        b.get("text", {}).get("text", "")
        for b in view.to_dict()["blocks"]
        if b.get("text")
    )
    assert "이미 북마크한 글이에요" in body_text


@pytest.mark.asyncio
async def test_bookmark_modal_for_new_content_opens_save_form(
    ack, fake_slack_client, factory, point_service_mock
) -> None:
    """✅ 신규 북마크 → 저장 폼 모달."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()
    service.get_content_by.return_value = factories.make_content(
        user_id="U_AUTHOR", ts="ts_1"
    )
    service.get_bookmark.return_value = None

    body = make_action_body(
        actions=[
            {
                "action_id": "bookmark_modal",
                "type": "button",
                "value": '{"user_id": "U_AUTHOR", "dt": "2025-01-01 10:00:00"}',
            }
        ]
    )

    await contents_events.bookmark_modal(
        ack=ack,
        body=body,
        client=fake_slack_client,
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    fake_slack_client.views_open.assert_awaited_once()
    view = fake_slack_client.views_open.await_args.kwargs["view"]
    assert view.callback_id == "bookmark_view"


@pytest.mark.asyncio
async def test_create_bookmark_view_calls_service_and_acks_update(
    ack, say, fake_slack_client, factory, point_service_mock
) -> None:
    """✅ 북마크 저장 폼 제출 → service.create_bookmark + ack(update)."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()

    body = make_view_body(
        user_id="U_X",
        callback_id="bookmark_view",
        private_metadata='{"content_user_id": "U_AUTHOR", "content_ts": "ts_1"}',
        state_values={
            "bookmark_note": {"text_input": {"value": "기억하고 싶은 글"}},
        },
    )

    await contents_events.create_bookmark_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        view=body["view"],
        say=say,
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    service.create_bookmark.assert_called_once_with(
        user_id="U_X",
        content_user_id="U_AUTHOR",
        content_ts="ts_1",
        note="기억하고 싶은 글",
    )
    # ack 가 두 번 호출됨 (실제 라우터 코드 그대로). 마지막 호출은 update 응답.
    last_kwargs = ack.await_args.kwargs
    assert last_kwargs["response_action"] == "update"


# ---------------------------------------------------------------------------
# 자기소개 (open_intro_modal, edit_intro_view, submit_intro_view)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_intro_modal_self_shows_edit_button(
    ack, fake_slack_client, factory, point_service_mock
) -> None:
    """✅ 본인의 자기소개 → 수정 버튼이 있는 모달."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()
    service.get_user.return_value = factory.make_user(user_id="U_X", intro="안녕")

    body = make_action_body(actions=[
        {"action_id": "intro_modal", "value": "U_X", "type": "button"}
    ])

    await contents_events.open_intro_modal(
        ack=ack,
        body=body,
        client=fake_slack_client,
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    view = fake_slack_client.views_open.await_args.kwargs["view"]
    assert view.callback_id == "edit_intro_view"


@pytest.mark.asyncio
async def test_open_intro_modal_other_no_edit_button(
    ack, fake_slack_client, factory, point_service_mock
) -> None:
    """🌀 다른 유저의 자기소개 → 수정 버튼 없음."""
    user = factory.make_user(user_id="U_X")
    other = factory.make_user(user_id="U_Y", intro="다른 사람")
    service = MagicMock()
    service.get_user.return_value = other

    body = make_action_body(actions=[
        {"action_id": "intro_modal", "value": "U_Y", "type": "button"}
    ])

    await contents_events.open_intro_modal(
        ack=ack,
        body=body,
        client=fake_slack_client,
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    view = fake_slack_client.views_open.await_args.kwargs["view"]
    assert view.callback_id is None


@pytest.mark.asyncio
async def test_edit_intro_view_responds_with_update_view(
    ack, say, fake_slack_client, factory, slack_service, point_service_mock
) -> None:
    """✅ 자기소개 수정 시작 → ack(response_action=update)."""
    user = factory.make_user(user_id="U_X", intro="기존 자기소개")
    body = make_view_body(user_id="U_X")

    await contents_events.edit_intro_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        view=body["view"],
        say=say,
        user=user,
        service=slack_service,
        point_service=point_service_mock,
    )

    kwargs = ack.await_args.kwargs
    assert kwargs["response_action"] == "update"
    assert kwargs["view"].callback_id == "submit_intro_view"


@pytest.mark.asyncio
async def test_submit_intro_view_calls_service_update(
    ack, say, fake_slack_client, factory, point_service_mock
) -> None:
    """✅ 자기소개 수정 완료 → service.update_user_intro 호출."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()

    body = make_view_body(
        user_id="U_X",
        state_values={
            "description": {"edit_intro": {"value": "새로운 자기소개입니다."}}
        },
    )

    await contents_events.submit_intro_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        view=body["view"],
        say=say,
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    service.update_user_intro.assert_called_once_with(
        "U_X", new_intro="새로운 자기소개입니다."
    )


# ---------------------------------------------------------------------------
# contents_modal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contents_modal_shows_other_user_contents(
    ack, fake_slack_client, factory, point_service_mock
) -> None:
    """✅ 다른 유저 콘텐츠 모달 → views_open."""
    other = factory.make_user(
        user_id="U_OTHER",
        contents=[factories.make_content(user_id="U_OTHER")],
    )
    service = MagicMock()
    service.get_user.return_value = other

    body = make_action_body(actions=[
        {"action_id": "contents_modal", "value": "U_OTHER", "type": "button"}
    ])

    await contents_events.contents_modal(
        ack=ack,
        body=body,
        client=fake_slack_client,
        service=service,
        point_service=point_service_mock,
    )

    fake_slack_client.views_open.assert_awaited_once()


# ---------------------------------------------------------------------------
# 북마크 페이지 / overflow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_bookmark_page_next(
    ack, fake_slack_client, factory, point_service_mock
) -> None:
    """✅ next_bookmark_page_action → page+1 + views_update."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()
    bookmarks = [factories.make_bookmark(content_ts=str(i)) for i in range(40)]
    contents = [
        factories.make_content(ts=str(i), content_url=f"https://e.com/{i}")
        for i in range(40)
    ]
    service.fetch_bookmarks.return_value = bookmarks
    service.fetch_contents_by_ids.return_value = contents

    body = make_action_body(
        actions=[{"action_id": "next_bookmark_page_action", "type": "button"}],
        view={"id": "V", "private_metadata": '{"page": 1}'},
    )
    body["type"] = "block_actions"

    await contents_events.handle_bookmark_page(
        ack=ack,
        body=body,
        say=AsyncMock(),
        client=fake_slack_client,
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    fake_slack_client.views_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_open_overflow_action_remove_bookmark(
    ack, fake_slack_client, factory, point_service_mock
) -> None:
    """✅ remove_bookmark → service.update_bookmark + 모달 갱신."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()

    body = make_action_body(
        actions=[
            {
                "action_id": "bookmark_overflow_action",
                "type": "overflow",
                "selected_option": {
                    "value": '{"action": "remove_bookmark", "content_ts": "ts_1"}'
                },
            }
        ],
        view={"id": "V", "private_metadata": '{"page": 1}'},
    )

    await contents_events.open_overflow_action(
        ack=ack,
        body=body,
        client=fake_slack_client,
        say=AsyncMock(),
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    service.update_bookmark.assert_called_once()
    fake_slack_client.views_update.assert_awaited_once()
    rendered = fake_slack_client.views_update.await_args.kwargs["view"].to_dict()
    body_text = "".join(
        b.get("text", {}).get("text", "")
        for b in rendered["blocks"]
        if b.get("text")
    )
    assert "북마크를 취소했어요" in body_text


@pytest.mark.asyncio
async def test_open_overflow_action_view_note_with_existing_note(
    ack, fake_slack_client, factory, point_service_mock
) -> None:
    """✅ view_note → 메모 텍스트 노출."""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()
    service.get_bookmark.return_value = factories.make_bookmark(
        user_id="U_X", content_ts="ts_1", note="좋은 글이었음"
    )

    body = make_action_body(
        actions=[
            {
                "action_id": "bookmark_overflow_action",
                "type": "overflow",
                "selected_option": {
                    "value": '{"action": "view_note", "content_ts": "ts_1"}'
                },
            }
        ],
        view={"id": "V", "private_metadata": '{"page": 1}'},
    )

    await contents_events.open_overflow_action(
        ack=ack,
        body=body,
        client=fake_slack_client,
        say=AsyncMock(),
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    rendered = fake_slack_client.views_update.await_args.kwargs["view"].to_dict()
    body_text = "".join(
        b.get("text", {}).get("text", "")
        for b in rendered["blocks"]
        if b.get("text")
    )
    assert "좋은 글이었음" in body_text


@pytest.mark.asyncio
async def test_open_overflow_action_view_note_without_note(
    ack, fake_slack_client, factory, point_service_mock
) -> None:
    """🌀 view_note + 메모 없음 → '메모가 없어요.'"""
    user = factory.make_user(user_id="U_X")
    service = MagicMock()
    service.get_bookmark.return_value = factories.make_bookmark(
        user_id="U_X", content_ts="ts_1", note=""
    )

    body = make_action_body(
        actions=[
            {
                "action_id": "bookmark_overflow_action",
                "type": "overflow",
                "selected_option": {
                    "value": '{"action": "view_note", "content_ts": "ts_1"}'
                },
            }
        ],
        view={"id": "V", "private_metadata": '{"page": 1}'},
    )

    await contents_events.open_overflow_action(
        ack=ack,
        body=body,
        client=fake_slack_client,
        say=AsyncMock(),
        user=user,
        service=service,
        point_service=point_service_mock,
    )

    rendered = fake_slack_client.views_update.await_args.kwargs["view"].to_dict()
    body_text = "".join(
        b.get("text", {}).get("text", "")
        for b in rendered["blocks"]
        if b.get("text")
    )
    assert "메모가 없어요" in body_text
