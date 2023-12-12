import re
import traceback
from app.config import settings
from slack_bolt.async_app import AsyncApp
from app.logging import log_event
from loguru import logger
from slack_bolt.request import BoltRequest
from slack_bolt.response import BoltResponse

from typing import Callable, cast

from app.slack.contents import events as contents_events
from app.slack.core import events as core_events
from app.slack.repositories import SlackRepository
from app.slack.services import SlackService

app = AsyncApp(token=settings.BOT_TOKEN)


@app.middleware
async def log_event_middleware(
    req: BoltRequest, resp: BoltResponse, next: Callable
) -> None:
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
async def inject_service_middleware(
    req: BoltRequest, resp: BoltResponse, next: Callable
) -> None:
    """서비스 객체를 주입합니다."""
    event = req.context.get("event")
    user_id = req.context.user_id
    channel_id = req.context.channel_id

    if event in ["app_mention", "message", "member_joined_channel"]:
        # 앱 멘션과 일반 메시지는 서비스 객체를 주입하지 않는다.
        await next()
        return

    user_repo = SlackRepository()
    user = user_repo.get_user(cast(str, user_id))
    if user:
        req.context["service"] = SlackService(user_repo=user_repo, user=user)
        await next()
        return

    # 사용자 정보가 없으면 안내 문구를 전송하고 관리자에게 알립니다.
    await app.client.chat_postEphemeral(
        channel=cast(str, channel_id),
        user=cast(str, user_id),
        text=f"🥲 아직 사용자 정보가 없어요...\
            \n👉🏼 <#{settings.SUPPORT_CHANNEL}> 채널로 문의해주시면 도와드릴게요!",
    )
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

    # 단순 값 에러는 무시합니다.
    if isinstance(error, ValueError):
        raise error

    # 사용자에게 에러를 알립니다.
    if re.search(r"[\u3131-\uD79D]", str(error)):
        # 한글로 핸들링하는 메시지만 사용자에게 전송합니다.
        message = str(error)
    else:
        message = "예기치 못한 오류가 발생했어요."
    await app.client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {"type": "plain_text", "text": "잠깐!"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🥲 {message}\n\n👉🏼 문제가 해결되지 않는다면 <#{settings.SUPPORT_CHANNEL}> 채널로 문의해주세요! ",  # noqa E501
                    },
                }
            ],
        },
    )

    # 관리자에게 에러를 알립니다.
    await app.client.chat_postMessage(
        channel=settings.ADMIN_CHANNEL, text=f"🫢: {error=} 🕊️: {trace=} 👉🏼 💌: {body=}"
    )


# community
@app.event("message")
async def handle_message(ack, body) -> None:
    user_id = body.get("event", {}).get("user")
    channel_id = body.get("event", {}).get("channel")
    is_thread = bool(body.get("event", {}).get("thread_ts"))

    if channel_id == settings.SUPPORT_CHANNEL and is_thread is False:
        # 사용자가 문의사항을 남기면 관리자에게 알립니다.
        if user := SlackRepository().get_user(cast(str, user_id)):
            message = f"👋🏼 <#{user.channel_id}>채널의 {user.name}님이 <#{channel_id}>을 남겼어요."
            await app.client.chat_postMessage(
                channel=settings.ADMIN_CHANNEL, text=message
            )

    await ack()


@app.event("member_joined_channel")
async def handle_member_joined_channel(ack, body) -> None:
    await ack()


# contents
app.command("/제출")(contents_events.submit_command)
app.view("submit_view")(contents_events.submit_view)
app.action("intro_modal")(contents_events.open_intro_modal)
app.view("edit_intro_view")(contents_events.edit_intro_view)
app.view("submit_intro_view")(contents_events.submit_intro_view)
app.action("contents_modal")(contents_events.contents_modal)
app.action("bookmark_modal")(contents_events.bookmark_modal)
app.view("bookmark_view")(contents_events.bookmark_view)
app.command("/패스")(contents_events.pass_command)
app.view("pass_view")(contents_events.pass_view)
app.command("/검색")(contents_events.search_command)
app.view("submit_search")(contents_events.submit_search)
app.view("back_to_search_view")(contents_events.back_to_search_view)
app.command("/북마크")(contents_events.bookmark_command)
app.view("bookmark_search_view")(contents_events.bookmark_search_view)
app.action("bookmark_overflow_action")(contents_events.open_overflow_action)
app.view("bookmark_submit_search_view")(contents_events.bookmark_submit_search_view)

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
    "edit_intro_view": "자기소개 수정 시작",
    "submit_intro_view": "자기소개 수정 완료",
    "contents_modal": "다른 유저의 제출한 글 목록 확인",
    "bookmark_modal": "북마크 저장 시작",
    "bookmark_view": "북마크 저장 완료",
    "/패스": "글 패스 시작",
    "pass_view": "글 패스 완료",
    "/검색": "글 검색 시작",
    "submit_search": "글 검색 완료",
    "back_to_search_view": "글 검색 다시 시작",
    "/북마크": "북마크 조회",
    "bookmark_search_view": "북마크 검색 시작",
    "bookmark_overflow_action": "북마크 메뉴 선택",
    "bookmark_submit_search_view": "북마크 검색 완료",
    "app_mention": "앱 멘션",
    "/예치금": "예치금 조회",
    "/제출내역": "제출내역 조회",
    "/관리자": "관리자 메뉴 조회",
    "/도움말": "도움말 조회",
}
