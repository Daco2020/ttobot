import re
import traceback
from app.config import settings
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from app.logging import log_event
from loguru import logger
from slack_bolt.request import BoltRequest
from slack_bolt.response import BoltResponse

from typing import Callable, cast

from app.slack.contents import events as contents_events
from app.slack.core import events as core_events
from app.slack.community import events as community_events
from app.slack.exception import BotException
from app.slack.repositories import SlackRepository
from app.slack.services import SlackService

app = AsyncApp(token=settings.BOT_TOKEN)


@app.middleware
async def log_event_middleware(req: BoltRequest, resp: BoltResponse, next: Callable) -> None:
    """이벤트를 로그로 남깁니다."""
    body = req.body
    if body.get("command"):
        event = body.get("command")
        type = "command"
    elif body.get("type") == "view_submission":
        event = body.get("view", {}).get("callback_id")
        type = "view_submission"
    elif body.get("type") == "block_actions":
        event = body.get("actions", [{}])[0].get("action_id")
        type = "block_actions"
    elif body.get("event"):
        event = body.get("event", {}).get("type")
        type = "event"
    else:
        event = "unknown"
        type = "unknown"

    if event not in ["message", "member_joined_channel"]:
        description = event_descriptions.get(str(event), "알 수 없는 이벤트")
        log_event(
            actor=req.context.user_id,
            event=event,  # type: ignore
            type=type,
            description=description,
            body=body,
        )

    req.context["event"] = event
    await next()


@app.middleware
async def inject_service_middleware(req: BoltRequest, resp: BoltResponse, next: Callable) -> None:
    """서비스 객체를 주입합니다."""
    event = req.context.get("event")
    user_id = req.context.user_id
    channel_id = req.context.channel_id

    if event in ["app_mention", "member_joined_channel"]:
        # 앱 멘션과 채널 입장은 서비스 객체를 주입하지 않는다.
        await next()
        return

    user_repo = SlackRepository()
    user = user_repo.get_user(cast(str, user_id))
    if user:
        req.context["service"] = SlackService(user_repo=user_repo, user=user)
        await next()
        return

    if user_id is None:
        # TODO: 추후 에러 코드 정의할 것
        raise BotException("사용자 아이디가 없습니다.")

    message = (
        "🥲 사용자 정보를 추가해주세요. 👉🏼 "
        f"event: `{event}` "
        f"channel: <#{channel_id}> "
        f"user_id: {user_id}"
    )
    await app.client.chat_postMessage(channel=settings.ADMIN_CHANNEL, text=message)
    logger.error(message)


@app.error
async def handle_error(error, body):
    """이벤트 핸들러에서 발생한 에러를 처리합니다."""
    logger.error(f'"{str(error)}"')
    trace = traceback.format_exc()
    logger.debug(dict(body=body, error=trace))

    # 단순 값 에러는 사용자에게 알리지 않습니다.
    if isinstance(error, ValueError):
        raise error

    # 일부 봇은 user_id 를 가지지 않기 때문에 무시합니다.
    if isinstance(error, BotException):
        if error.message == "사용자 아이디가 없습니다.":
            return

    # 사용자에게 에러를 알립니다.
    if re.search(r"[\u3131-\uD79D]", str(error)):
        # 한글로 핸들링하는 메시지만 사용자에게 전송합니다.
        message = str(error)
    else:
        message = "예기치 못한 오류가 발생했어요."

    if trigger_id := body.get("trigger_id"):
        await app.client.views_open(
            trigger_id=trigger_id,
            view={
                "type": "modal",
                "title": {"type": "plain_text", "text": "잠깐!"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"🥲 {message}\n\n👉🏼 궁금한 사항은 <#{settings.SUPPORT_CHANNEL}> 채널로 문의해주세요.",  # noqa E501
                        },
                    }
                ],
            },
        )

    # 관리자에게 에러를 알립니다.
    await app.client.chat_postMessage(
        channel=settings.ADMIN_CHANNEL,
        text=f"🫢: {error=} 🕊️: {trace=} 👉🏼 💌: {body=}",
    )


# community
app.command("/저장키워드등록")(community_events.trigger_command)
app.view("trigger_view")(community_events.trigger_view)


@app.event("message")
async def handle_message(ack, body, client: AsyncWebClient, service: SlackService) -> None:
    await ack()

    event = body.get("event", {})
    user_id = event.get("user")
    channel_id = event.get("channel")
    thread_ts = event.get("thread_ts")

    if channel_id == settings.SUPPORT_CHANNEL and not thread_ts:
        # 사용자가 문의사항을 남기면 관리자에게 알립니다.
        if user := SlackRepository().get_user(cast(str, user_id)):
            message = f"👋🏼 <#{user.channel_id}>채널의 {user.name}님이 <#{channel_id}>을 남겼어요."
            await client.chat_postMessage(channel=settings.ADMIN_CHANNEL, text=message)

    await community_events.handle_trigger_message(client, event, service)


@app.event("member_joined_channel")
async def handle_member_joined_channel(ack, body) -> None:
    await ack()


# contents
app.command("/제출")(contents_events.submit_command)
app.view("submit_view")(contents_events.submit_view)
app.action("intro_modal")(contents_events.open_intro_modal)
app.action("forward_message")(contents_events.forward_message)
app.view("edit_intro_view")(contents_events.edit_intro_view)
app.view("submit_intro_view")(contents_events.submit_intro_view)
app.action("contents_modal")(contents_events.contents_modal)
app.action("bookmark_modal")(contents_events.bookmark_modal)
app.view("bookmark_view")(contents_events.bookmark_view)
app.command("/패스")(contents_events.pass_command)
app.view("pass_view")(contents_events.pass_view)
app.command("/검색")(contents_events.search_command)
app.view("submit_search")(contents_events.submit_search)
app.action("web_search")(contents_events.submit_search)
app.view("back_to_search_view")(contents_events.back_to_search_view)
app.command("/북마크")(contents_events.bookmark_command)
app.action("bookmark_overflow_action")(contents_events.open_overflow_action)
app.action("next_bookmark_page_action")(contents_events.handle_bookmark_page)
app.action("prev_bookmark_page_action")(contents_events.handle_bookmark_page)
app.view("handle_bookmark_page_view")(contents_events.handle_bookmark_page)
# app.view("bookmark_search_view")(contents_events.bookmark_search_view)
# app.view("bookmark_submit_search_view")(contents_events.bookmark_submit_search_view)

# core
app.event("app_mention")(core_events.handle_app_mention)
app.command("/예치금")(core_events.get_deposit)
app.command("/제출내역")(core_events.history_command)
app.command("/관리자")(core_events.admin_command)
app.command("/도움말")(core_events.help_command)


event_descriptions = {
    "/제출": "글 제출 시작",
    "submit_view": "글 제출 완료",
    "intro_modal": "다른 유저의 자기소개 확인",
    "forward_message": "다른 채널로 메시지 전송",
    "edit_intro_view": "자기소개 수정 시작",
    "submit_intro_view": "자기소개 수정 완료",
    "contents_modal": "다른 유저의 제출한 글 목록 확인",
    "bookmark_modal": "북마크 저장 시작",
    "bookmark_view": "북마크 저장 완료",
    "/패스": "글 패스 시작",
    "pass_view": "글 패스 완료",
    "/검색": "글 검색 시작",
    "submit_search": "글 검색 완료",
    "web_search": "웹 검색 시작",
    "back_to_search_view": "글 검색 다시 시작",
    "/북마크": "북마크 조회",
    "bookmark_overflow_action": "북마크 메뉴 선택",
    "next_bookmark_page_action": "다음 북마크 페이지",
    "prev_bookmark_page_action": "이전 북마크 페이지",
    "handle_bookmark_page_view": "북마크 페이지 이동",
    # "bookmark_search_view": "북마크 검색 시작",
    # "bookmark_submit_search_view": "북마크 검색 완료",
    "app_mention": "앱 멘션",
    "/예치금": "예치금 조회",
    "/제출내역": "제출내역 조회",
    "/관리자": "관리자 메뉴 조회",
    "/도움말": "도움말 조회",
    "/저장키워드등록": "저장할 키워드 등록 시작",
    "/trigger_view": "저장할 키워드 등록 완료",
}
