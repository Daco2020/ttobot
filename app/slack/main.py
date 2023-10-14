import traceback
from app.config import PASS_VIEW, SUBMIT_VIEW, settings
from slack_bolt.async_app import AsyncApp
from app.logging import log_event
from loguru import logger
from slack_bolt.request import BoltRequest
from slack_bolt.response import BoltResponse
from typing import Callable

from app.slack.community import events as community_events
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
    user_id = req.context.get("user_id")
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

    if event != "message":  # 일반 메시지는 제외
        description = descriptions.get(str(event), "알 수 없는 이벤트")
        log_event(user_id, event, type, description)  # type: ignore

    await next()


@app.middleware
async def inject_middleware(
    req: BoltRequest, resp: BoltResponse, next: Callable
) -> None:
    """서비스 객체를 주입합니다."""
    user_id = req.context.get("user_id")
    user_repo = SlackRepository()
    user = user_repo.get_user(user_id)  # type: ignore
    if not user:
        await app.client.views_open(
            trigger_id=req.body["trigger_id"],
            view={
                "type": "modal",
                "title": {"type": "plain_text", "text": "또봇"},
                "close": {"type": "plain_text", "text": "닫기"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "🥲 사용자 정보가 등록되어 있지 않습니다.\n[0_글또봇질문] 채널로 문의해주세요.",
                        },
                    },
                ],
            },
        )
        message = f"🥲 사용자 정보가 등록되어 있지 않습니다. {user_id=}"
        logger.error(message)
        await app.client.chat_postMessage(channel=settings.ADMIN_CHANNEL, text=message)
        return

    req.context["service"] = SlackService(user_repo=SlackRepository(), user=user)
    await next()


@app.error
async def handle_error(error, body):
    """이벤트 핸들러에서 발생한 에러를 처리합니다."""
    logger.error(f'"{str(error)}"')
    trace = traceback.format_exc()
    logger.debug(dict(body=body, error=trace))
    await app.client.chat_postMessage(
        channel=settings.ADMIN_CHANNEL, text=f"{trace=} {'>'*100} {body=}"
    )


@app.event("message")
async def handle_message_event(ack, body) -> None:
    await ack()


# community
app.command("/모코숲")(community_events.guide_command)
app.event("member_joined_channel")(community_events.send_welcome_message)

# contents
app.command("/제출")(contents_events.submit_command)
app.view(SUBMIT_VIEW)(contents_events.submit_view)
app.action("intro_modal")(contents_events.open_intro_modal)
app.action("contents_modal")(contents_events.contents_modal)
app.action("bookmark_modal")(contents_events.bookmark_modal)
app.view("bookmark_view")(contents_events.bookmark_view)
app.command("/패스")(contents_events.pass_command)
app.view(PASS_VIEW)(contents_events.pass_view)
app.command("/검색")(contents_events.search_command)
app.view("submit_search")(contents_events.submit_search)
app.view("back_to_search_view")(contents_events.back_to_search_view)
app.command("/북마크")(contents_events.bookmark_command)
app.view("bookmark_search_view")(contents_events.bookmark_search_view)
app.action("bookmark_overflow_action")(contents_events.open_overflow_action)
app.view("bookmark_submit_search_view")(contents_events.bookmark_submit_search_view)

# core
app.event("app_mention")(core_events.handle_mention)
app.command("/예치금")(core_events.get_deposit)
app.command("/제출내역")(core_events.history_command)
app.command("/관리자")(core_events.admin_command)


descriptions = {
    "/제출": "글 제출 시작",
    SUBMIT_VIEW: "글 제출 완료",
    "intro_modal": "다른 유저의 자기소개 확인",
    "contents_modal": "다른 유저의 제출한 글 목록 확인",
    "bookmark_modal": "북마크 저장 시작",
    "bookmark_view": "북마크 저장 완료",
    "/패스": "글 패스 시작",
    PASS_VIEW: "글 패스 완료",
    "/검색": "글 검색 시작",
    "submit_search": "글 검색 완료",
    "back_to_search_view": "글 검색 다시 시작",
    "/북마크": "북마크 조회",
    "bookmark_search_view": "북마크 검색 시작",
    "bookmark_overflow_action": "북마크 메뉴 선택",
    "bookmark_submit_search_view": "북마크 검색 완료",
    "/모코숲": "모코숲 가이드 조회",
    "member_joined_channel": "모코숲 채널 입장",
    "app_mention": "앱 멘션",
    "/예치금": "예치금 조회",
    "/제출내역": "제출내역 조회",
    "/관리자": "관리자 메뉴 조회",
}
