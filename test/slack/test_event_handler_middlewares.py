"""슬랙 event_handler 의 미들웨어 / 에러 핸들러 테스트.

대상: app/slack/event_handler.py
- log_event_middleware
- dependency_injection_middleware
- handle_error

`BoltRequest` 와 `BoltContext` 를 진짜로 만들 필요 없이, 가벼운 fake 클래스로 대체한다.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.exception import BotException
from app.slack import event_handler
from test import factories


class FakeContext(dict):
    """req.context.user_id 와 req.context["service"] 양쪽 접근을 모두 지원."""

    def __init__(self, user_id=None, channel_id=None):
        super().__init__()
        self.user_id = user_id
        self.channel_id = channel_id


class FakeRequest:
    """BoltRequest 의 .body / .context 만 흉내내는 가벼운 객체."""

    def __init__(self, body, user_id=None, channel_id=None):
        self.body = body
        self.context = FakeContext(user_id=user_id, channel_id=channel_id)


# ---------------------------------------------------------------------------
# log_event_middleware
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_event_middleware_command(mocker) -> None:
    """✅ command body → event=명령어, type=command 로 로깅."""
    log_event_mock = mocker.patch("app.slack.event_handler.log_event")
    req = FakeRequest({"command": "/제출"}, user_id="U_X")
    next_mock = AsyncMock()

    await event_handler.log_event_middleware(req=req, resp=None, next=next_mock)

    log_event_mock.assert_called_once()
    kwargs = log_event_mock.call_args.kwargs
    assert kwargs["actor"] == "U_X"
    assert kwargs["event"] == "/제출"
    assert kwargs["type"] == "command"
    assert kwargs["description"] == "글 제출 시작"
    assert req.context["event"] == "/제출"
    next_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_log_event_middleware_view_submission(mocker) -> None:
    """✅ view_submission body → callback_id 로 로깅."""
    log_event_mock = mocker.patch("app.slack.event_handler.log_event")
    req = FakeRequest(
        {"type": "view_submission", "view": {"callback_id": "submit_view"}},
        user_id="U_X",
    )

    await event_handler.log_event_middleware(req=req, resp=None, next=AsyncMock())

    kwargs = log_event_mock.call_args.kwargs
    assert kwargs["event"] == "submit_view"
    assert kwargs["type"] == "view_submission"
    assert kwargs["description"] == "글 제출 완료"


@pytest.mark.asyncio
async def test_log_event_middleware_block_actions(mocker) -> None:
    """✅ block_actions body → action_id 로 로깅."""
    log_event_mock = mocker.patch("app.slack.event_handler.log_event")
    req = FakeRequest(
        {"type": "block_actions", "actions": [{"action_id": "intro_modal"}]},
        user_id="U_X",
    )

    await event_handler.log_event_middleware(req=req, resp=None, next=AsyncMock())

    kwargs = log_event_mock.call_args.kwargs
    assert kwargs["event"] == "intro_modal"
    assert kwargs["type"] == "block_actions"


@pytest.mark.asyncio
async def test_log_event_middleware_event_callback(mocker) -> None:
    """✅ event body → event.type 로 로깅."""
    log_event_mock = mocker.patch("app.slack.event_handler.log_event")
    req = FakeRequest(
        {"event": {"type": "app_mention"}},
        user_id="U_X",
    )

    await event_handler.log_event_middleware(req=req, resp=None, next=AsyncMock())

    kwargs = log_event_mock.call_args.kwargs
    assert kwargs["event"] == "app_mention"
    assert kwargs["type"] == "event"


@pytest.mark.asyncio
async def test_log_event_middleware_skips_message_event(mocker) -> None:
    """⚠️ event=message → 로깅 우회 (handle_message 가 별도로 처리)."""
    log_event_mock = mocker.patch("app.slack.event_handler.log_event")
    req = FakeRequest(
        {"event": {"type": "message"}},
        user_id="U_X",
    )
    next_mock = AsyncMock()

    await event_handler.log_event_middleware(req=req, resp=None, next=next_mock)

    log_event_mock.assert_not_called()
    next_mock.assert_awaited_once()
    # event 컨텍스트는 여전히 설정되어야 한다
    assert req.context["event"] == "message"


@pytest.mark.asyncio
async def test_log_event_middleware_skips_reaction_added(mocker) -> None:
    """⚠️ event=reaction_added → 로깅 우회."""
    log_event_mock = mocker.patch("app.slack.event_handler.log_event")
    req = FakeRequest({"event": {"type": "reaction_added"}}, user_id="U_X")

    await event_handler.log_event_middleware(req=req, resp=None, next=AsyncMock())

    log_event_mock.assert_not_called()


@pytest.mark.asyncio
async def test_log_event_middleware_unknown_body(mocker) -> None:
    """🌀 알 수 없는 body 모양 → event='unknown', type='unknown'."""
    log_event_mock = mocker.patch("app.slack.event_handler.log_event")
    req = FakeRequest({"some": "weird"}, user_id="U_X")

    await event_handler.log_event_middleware(req=req, resp=None, next=AsyncMock())

    kwargs = log_event_mock.call_args.kwargs
    assert kwargs["event"] == "unknown"
    assert kwargs["type"] == "unknown"


# ---------------------------------------------------------------------------
# dependency_injection_middleware
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dependency_injection_for_message_event_skips(mocker) -> None:
    """✅ event=message → 의존성 주입 없이 next() 즉시 호출."""
    repo_mock = mocker.patch("app.slack.event_handler.SlackRepository")
    req = FakeRequest({})
    req.context["event"] = "message"
    next_mock = AsyncMock()

    await event_handler.dependency_injection_middleware(
        req=req, resp=None, next=next_mock
    )

    next_mock.assert_awaited_once()
    # 의존성 주입이 일어나지 않아야 한다
    repo_mock.assert_not_called()
    assert "service" not in req.context


@pytest.mark.asyncio
async def test_dependency_injection_for_app_mention_skips(mocker) -> None:
    """✅ event=app_mention → 의존성 주입 우회."""
    repo_mock = mocker.patch("app.slack.event_handler.SlackRepository")
    req = FakeRequest({})
    req.context["event"] = "app_mention"

    await event_handler.dependency_injection_middleware(
        req=req, resp=None, next=AsyncMock()
    )

    repo_mock.assert_not_called()


@pytest.mark.asyncio
async def test_dependency_injection_for_known_user(mocker) -> None:
    """✅ 일반 이벤트 + 등록 유저 → service/point_service/user 주입."""
    user = factories.make_user(user_id="U_X")
    repo_instance = MagicMock()
    repo_instance.get_user.return_value = user
    mocker.patch(
        "app.slack.event_handler.SlackRepository", return_value=repo_instance
    )

    req = FakeRequest({}, user_id="U_X", channel_id="C_X")
    req.context["event"] = "/제출"
    next_mock = AsyncMock()

    await event_handler.dependency_injection_middleware(
        req=req, resp=None, next=next_mock
    )

    next_mock.assert_awaited_once()
    assert req.context["user"] is user
    assert req.context["service"] is not None
    assert req.context["point_service"] is not None


@pytest.mark.asyncio
async def test_dependency_injection_for_app_home_opened_unknown_user(mocker) -> None:
    """✅ app_home_opened + 미등록 유저 → service/point_service/user 모두 None 으로 주입."""
    repo_instance = MagicMock()
    repo_instance.get_user.return_value = None
    mocker.patch(
        "app.slack.event_handler.SlackRepository", return_value=repo_instance
    )

    req = FakeRequest({}, user_id="U_GHOST", channel_id="C_X")
    req.context["event"] = "app_home_opened"
    next_mock = AsyncMock()

    await event_handler.dependency_injection_middleware(
        req=req, resp=None, next=next_mock
    )

    next_mock.assert_awaited_once()
    assert req.context["service"] is None
    assert req.context["point_service"] is None
    assert req.context["user"] is None


@pytest.mark.asyncio
async def test_dependency_injection_for_unknown_user_other_event_raises(
    mocker,
) -> None:
    """⚠️ 미등록 유저 + 일반 이벤트 → 관리자 채널 알림 + BotException."""
    repo_instance = MagicMock()
    repo_instance.get_user.return_value = None
    mocker.patch(
        "app.slack.event_handler.SlackRepository", return_value=repo_instance
    )

    chat_post_mock = mocker.patch.object(
        event_handler.app.client, "chat_postMessage", new=AsyncMock()
    )

    req = FakeRequest({}, user_id="U_GHOST", channel_id="C_X")
    req.context["event"] = "/제출"  # app_home_opened 도, bypass 도 아님

    with pytest.raises(BotException) as exc_info:
        await event_handler.dependency_injection_middleware(
            req=req, resp=None, next=AsyncMock()
        )
    assert "사용자 정보를 찾을 수 없어요" in str(exc_info.value)
    chat_post_mock.assert_awaited_once()
    kwargs = chat_post_mock.await_args.kwargs
    assert kwargs["channel"] == settings.ADMIN_CHANNEL
    assert "U_GHOST" in kwargs["text"]


@pytest.mark.asyncio
async def test_dependency_injection_for_user_id_none_returns_silently(
    mocker,
) -> None:
    """🌀 user_id 가 None (일부 슬랙 봇) → 아무 동작 없이 종료."""
    repo_instance = MagicMock()
    repo_instance.get_user.return_value = None
    mocker.patch(
        "app.slack.event_handler.SlackRepository", return_value=repo_instance
    )

    chat_post_mock = mocker.patch.object(
        event_handler.app.client, "chat_postMessage", new=AsyncMock()
    )

    req = FakeRequest({}, user_id=None, channel_id="C_X")
    req.context["event"] = "/제출"
    next_mock = AsyncMock()

    # 예외 없이 그냥 종료
    await event_handler.dependency_injection_middleware(
        req=req, resp=None, next=next_mock
    )

    chat_post_mock.assert_not_called()
    next_mock.assert_not_called()


# ---------------------------------------------------------------------------
# handle_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_error_with_korean_message_shows_to_user(mocker) -> None:
    """✅ 한국어 에러 → 사용자 모달 + 관리자 채널 알림."""
    views_open_mock = mocker.patch.object(
        event_handler.app.client, "views_open", new=AsyncMock()
    )
    chat_post_mock = mocker.patch.object(
        event_handler.app.client, "chat_postMessage", new=AsyncMock()
    )

    error = BotException("이미 인증한 글이에요.")
    body = {"trigger_id": "trigger_123"}

    await event_handler.handle_error(error=error, body=body)

    views_open_mock.assert_awaited_once()
    view = views_open_mock.await_args.kwargs["view"]
    rendered = view.to_dict()
    body_text = "".join(
        b.get("text", {}).get("text", "")
        for b in rendered["blocks"]
        if b.get("text")
    )
    assert "이미 인증한 글이에요" in body_text
    chat_post_mock.assert_awaited_once()
    admin_kwargs = chat_post_mock.await_args.kwargs
    assert admin_kwargs["channel"] == settings.ADMIN_CHANNEL


@pytest.mark.asyncio
async def test_handle_error_with_english_message_shows_generic(mocker) -> None:
    """✅ 영문 에러 → '예기치 못한 오류' 메시지로 노출."""
    views_open_mock = mocker.patch.object(
        event_handler.app.client, "views_open", new=AsyncMock()
    )
    mocker.patch.object(
        event_handler.app.client, "chat_postMessage", new=AsyncMock()
    )

    error = RuntimeError("KeyError: 'foo'")
    body = {"trigger_id": "trigger_X"}

    await event_handler.handle_error(error=error, body=body)

    rendered = views_open_mock.await_args.kwargs["view"].to_dict()
    body_text = "".join(
        b.get("text", {}).get("text", "")
        for b in rendered["blocks"]
        if b.get("text")
    )
    assert "예기치 못한 오류가 발생했어요" in body_text


@pytest.mark.asyncio
async def test_handle_error_value_error_reraises(mocker) -> None:
    """⚠️ ValueError → 그대로 raise (사용자 알림 없음)."""
    views_open_mock = mocker.patch.object(
        event_handler.app.client, "views_open", new=AsyncMock()
    )
    chat_post_mock = mocker.patch.object(
        event_handler.app.client, "chat_postMessage", new=AsyncMock()
    )

    error = ValueError("값 오류")

    with pytest.raises(ValueError):
        await event_handler.handle_error(error=error, body={"trigger_id": "x"})

    views_open_mock.assert_not_called()
    chat_post_mock.assert_not_called()


@pytest.mark.asyncio
async def test_handle_error_without_trigger_id_skips_modal(mocker) -> None:
    """🌀 trigger_id 없음 → views_open 호출 안 함, 관리자 알림만."""
    views_open_mock = mocker.patch.object(
        event_handler.app.client, "views_open", new=AsyncMock()
    )
    chat_post_mock = mocker.patch.object(
        event_handler.app.client, "chat_postMessage", new=AsyncMock()
    )

    error = BotException("어떤 한국어 에러")

    await event_handler.handle_error(error=error, body={})

    views_open_mock.assert_not_called()
    chat_post_mock.assert_awaited_once()
    assert chat_post_mock.await_args.kwargs["channel"] == settings.ADMIN_CHANNEL
