import os
import re
import traceback
from app.config import settings
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from app.logging import log_event
from loguru import logger
from slack_bolt.request import BoltRequest
from slack_bolt.response import BoltResponse
from slack_bolt.async_app import AsyncAck, AsyncSay
from slack_sdk.models.blocks import SectionBlock
from slack_sdk.models.views import View

from typing import Any, Callable, cast

from app.slack.events import community as community_events
from app.slack.events import contents as contents_events
from app.slack.events import core as core_events
from app.slack.events import log as log_events
from app.slack.events import subscriptions as subscriptions_events
from app.exception import BotException
from app.slack.events.writing_participation import (
    open_writing_participation_view,
    submit_writing_participation_view,
)
from app.slack.repositories import SlackRepository
from app.slack.services.base import SlackService
from app.slack.services.point import PointService
from app.slack.types import MessageBodyType


# slack_bolt 은 이 두 값이 환경변수로 있으면 파일 기반 OAuth 설치(다중 워크스페이스) 모드를 스스로
# 켠다. 또봇은 봇 토큰 단일 워크스페이스이고 두 값은 웹 로그인용(login.py 가 settings 로 직접 씀)이다.
# Koyeb 처럼 진짜 환경변수로 주입되면 설치 기록을 찾다 모든 요청이 실패하므로 생성 중에만 숨긴다.
_BOLT_OAUTH_ENV_KEYS = ("SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET")


def create_slack_app() -> AsyncApp:
    """봇 토큰 기반 단일 워크스페이스 슬랙 앱을 만든다. OAuth 자동 설정은 막는다."""
    hidden = {k: os.environ.pop(k) for k in _BOLT_OAUTH_ENV_KEYS if k in os.environ}
    try:
        return AsyncApp(
            client=AsyncWebClient(
                token=settings.SLACK_BOT_TOKEN,
                timeout=8,
            ),
        )
    finally:
        os.environ.update(hidden)


app = create_slack_app()


@app.middleware
async def log_event_middleware(
    req: BoltRequest,
    resp: BoltResponse,
    next: Callable,
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

    if event not in [
        "message",
        "member_joined_channel",
        "reaction_added",
        "reaction_removed",
    ]:
        # message 와 reaction 은 handle 함수에서 별도로 로깅합니다.
        description = event_descriptions.get(str(event), "알 수 없는 이벤트")

        # 종이비행기 메시지 전송 완료 이벤트는 내용을 로그에 포함시키지 않는다.
        if description == "종이비행기 메시지 전송 완료":
            req.context["event"] = event
            await next()

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
async def dependency_injection_middleware(
    req: BoltRequest,
    resp: BoltResponse,
    next: Callable,
) -> None:
    """서비스 객체를 주입합니다."""
    event = req.context.get("event")
    user_id = req.context.user_id
    channel_id = req.context.channel_id

    if event in [
        "app_mention",
        "channel_created",
        "member_joined_channel",
        "reaction_added",
        "reaction_removed",
        "message",
    ]:
        # 해당 이벤트는 의존성 주입을 하지 않습니다.
        # 메시지의 경우 handle_message 에서 의존성 주입을 합니다.
        await next()
        return

    repo = SlackRepository()
    user = repo.get_user(cast(str, user_id))
    if user:
        req.context["service"] = SlackService(repo=repo, user=user)
        req.context["point_service"] = PointService(repo=repo)
        req.context["user"] = user
        await next()
        return

    # TODO: 10기 멤버 등록 후에는 불필요하므로 제거
    if event == "app_home_opened":
        # 등록되지 않는 멤버는 의존성을 주입하지 않습니다.
        req.context["service"] = None
        req.context["point_service"] = None
        req.context["user"] = None
        await next()
        return

    if user_id is None:
        # 일부 슬랙 봇은 사용자 아이디가 없을 수 있습니다.
        return

    message = (
        "🥲 사용자 정보를 추가해주세요. 👉🏼 "
        f"event: `{event}` "
        f"channel: <#{channel_id}> "
        f"user_id: {user_id}"
    )
    await app.client.chat_postMessage(channel=settings.ADMIN_CHANNEL, text=message)
    logger.error(message)
    raise BotException("사용자 정보를 찾을 수 없어요.")


@app.error
async def handle_error(error, body):
    """이벤트 핸들러에서 발생한 에러를 처리합니다."""
    logger.error(f'"{str(error)}"')
    trace = traceback.format_exc()
    logger.debug(dict(body=body, error=trace))

    # 단순 값 에러는 사용자에게 알리지 않습니다.
    if isinstance(error, ValueError):
        raise error

    # 사용자에게 에러를 알립니다.
    if re.search(r"[\u3131-\uD79D]", str(error)):
        # 한글로 핸들링하는 메시지만 사용자에게 전송합니다.
        message = str(error)
    else:
        message = "예기치 못한 오류가 발생했어요."

    text = f"🥲 {message}\n\n👉🏼 문제가 해결되지 않는다면 <#{settings.BOT_SUPPORT_CHANNEL}> 채널로 문의해주세요."
    if trigger_id := body.get("trigger_id"):
        await app.client.views_open(
            trigger_id=trigger_id,
            view=View(
                type="modal",
                title={"type": "plain_text", "text": "잠깐!"},
                blocks=[SectionBlock(text=text)],
            ),
        )

    # 관리자에게 에러를 알립니다.
    await app.client.chat_postMessage(
        channel=settings.ADMIN_CHANNEL,
        text=f"🫢: {error=} 🕊️: {trace=} 👉🏼 💌: {body=}",
    )


@app.event("message")
async def handle_message(
    ack: AsyncAck,
    body: MessageBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
) -> None:
    await ack()

    event: dict[str, Any]
    subtype: str | None
    user_id: str
    channel_id: str
    thread_ts: str | None
    ts: str
    is_thread: bool

    event = body.get("event", {})  # type: ignore
    subtype = event.get("subtype")

    # 1. 메시지 타입에 따른 변수 할당
    # 1-1. 메시지 수정 및 파일 공유 외의 subtype 이벤트는 처리하지 않습니다.
    # 자세한 subtype 이 궁금하다면 https://api.slack.com/events/message 참고.
    if subtype and subtype not in ["message_changed", "file_share"]:
        return

    # 1-2. 메시지 수정 이벤트를 처리합니다.
    elif subtype == "message_changed":
        # 이미 봇이 댓글을 단 경우는 커피챗 인증 절차가 진행된 경우이므로 처리하지 않습니다.
        if settings.TTOBOT_USER_ID in event.get("message", {}).get("reply_users", []):
            return

        user_id = event.get("message", {}).get("user")
        channel_id = event["channel"]
        thread_ts = event.get("message", {}).get("thread_ts")
        ts = event.get("message", {}).get("ts")
        is_thread = thread_ts != ts if thread_ts else False

    # 1-3. subtype 이 file_share 이거나 없는 경우를 처리합니다.
    else:
        user_id = event["user"]
        channel_id = event["channel"]
        thread_ts = event.get("thread_ts")
        ts = event["ts"]
        is_thread = thread_ts != ts if thread_ts else False

        if is_thread:
            await log_events.handle_comment_data(body=body)
        else:  # TODO: 댓글이 post_data 로 들어오는 경우가 있는지 확인 필요.
            await log_events.handle_post_data(body=body)

    # 2. user_id 가 없는 이벤트(일부 슬랙 봇)는 처리하지 않습니다.
    if user_id is None:
        return

    # 3. 사용자가 문의사항을 남기면 관리자에게 알립니다.
    if (
        channel_id in [settings.BOT_SUPPORT_CHANNEL, settings.SUPPORT_CHANNEL]
        and not is_thread
        and subtype != "message_changed"
    ):
        repo = SlackRepository()
        user = repo.get_user(user_id)
        if not user:
            await _notify_missing_user_info(client, user_id)
            return

        message = f"👋🏼 <#{user.writing_channel_id}>채널의 {user.name}님이 <#{channel_id}>을 남겼어요. 👀 <@{settings.SUPER_ADMIN}> <@{settings.ADMIN_IDS[1]}>"
        await client.chat_postMessage(channel=settings.ADMIN_CHANNEL, text=message)
        return

    # 4. 커피챗 인증 메시지를 처리합니다.
    elif channel_id == settings.COFFEE_CHAT_PROOF_CHANNEL:
        repo = SlackRepository()
        user = repo.get_user(user_id)
        if not user:
            await _notify_missing_user_info(client, user_id)
            return

        description = event_descriptions.get(
            "coffee_chat_proof_message", "알 수 없는 이벤트"
        )
        log_event(
            actor=user.user_id,
            event="coffee_chat_proof_message",
            type="message",
            description=description,
            body=body,
        )

        service = SlackService(repo=repo, user=user)
        point_service = PointService(repo=repo)
        await community_events.handle_coffee_chat_message(
            ack=ack,
            body=body,
            say=say,
            client=client,
            user=user,
            service=service,
            point_service=point_service,
            subtype=subtype,
            is_thread=is_thread,
            ts=ts,
        )
        return


async def _notify_missing_user_info(client: AsyncWebClient, user_id: str):
    text = f"🥲 사용자 정보를 추가해주세요. 👉🏼 user_id: {user_id}"
    await client.chat_postMessage(channel=settings.ADMIN_CHANNEL, text=text)
    logger.error(text)


@app.event("member_joined_channel")
async def handle_member_joined_channel(ack, body) -> None:
    await ack()


# community
app.action("cancel_coffee_chat_proof_button")(
    community_events.cancel_coffee_chat_proof_button
)
app.action("submit_coffee_chat_proof_button")(
    community_events.submit_coffee_chat_proof_button
)
app.view("submit_coffee_chat_proof_view")(
    community_events.submit_coffee_chat_proof_view
)
app.command("/종이비행기")(community_events.paper_plane_command)

# contents
app.command("/제출")(contents_events.submit_command)
app.view("submit_view")(contents_events.submit_view)
app.action("intro_modal")(contents_events.open_intro_modal)
# app.action("forward_message")(contents_events.forward_message)
app.view("edit_intro_view")(contents_events.edit_intro_view)
app.view("submit_intro_view")(contents_events.submit_intro_view)
app.action("contents_modal")(contents_events.contents_modal)
app.action("bookmark_modal")(contents_events.bookmark_modal)
app.view("bookmark_view")(contents_events.create_bookmark_view)
app.command("/패스")(contents_events.pass_command)
app.view("pass_view")(contents_events.pass_view)
app.command("/검색")(contents_events.search_command)
app.view("submit_search")(contents_events.submit_search)
app.action("web_search")(contents_events.web_search)
app.view("back_to_search_view")(contents_events.back_to_search_view)
app.command("/북마크")(contents_events.bookmark_command)
app.action("open_bookmark_page_view")(contents_events.bookmark_page_view)
app.action("bookmark_overflow_action")(contents_events.open_overflow_action)
app.action("next_bookmark_page_action")(contents_events.handle_bookmark_page)
app.action("prev_bookmark_page_action")(contents_events.handle_bookmark_page)
app.view("handle_bookmark_page_view")(contents_events.handle_bookmark_page)

# core
app.event("app_mention")(core_events.handle_app_mention)
app.event("channel_created")(core_events.handle_channel_created)
app.command("/예치금")(core_events.open_deposit_view)
app.command("/제출내역")(core_events.open_submission_history_view)
app.command("/도움말")(core_events.open_help_view)
app.command("/관리자")(core_events.admin_command)
app.action("sync_store_select")(core_events.handle_sync_store)
app.action("invite_channel")(core_events.handle_invite_channel)
app.view("invite_channel_view")(core_events.handle_invite_channel_view)
app.event("app_home_opened")(core_events.handle_home_tab)
app.action("open_deposit_view")(core_events.open_deposit_view)
app.action("open_submission_history_view")(core_events.open_submission_history_view)
app.action("open_help_view")(core_events.open_help_view)
app.action("open_point_history_view")(core_events.open_point_history_view)
app.action("open_point_guide_view")(core_events.open_point_guide_view)
app.action("send_paper_plane_message")(core_events.send_paper_plane_message)
app.action("open_paper_plane_url")(core_events.open_paper_plane_url)
app.view("send_paper_plane_message_view")(core_events.send_paper_plane_message_view)
app.action("open_paper_plane_guide_view")(core_events.open_paper_plane_guide_view)
app.action("open_coffee_chat_history_view")(core_events.open_coffee_chat_history_view)
app.action("download_point_history")(core_events.download_point_history)
app.action("download_coffee_chat_history")(core_events.download_coffee_chat_history)
app.action("download_submission_history")(core_events.download_submission_history)
app.action("open_subscribe_member_view")(
    subscriptions_events.open_subscribe_member_view
)
app.action("subscribe_member")(subscriptions_events.subscribe_member)
app.action("unsubscribe_member")(subscriptions_events.unsubscribe_member)

# log
app.event("reaction_added")(log_events.handle_reaction_added)
app.event("reaction_removed")(log_events.handle_reaction_removed)
app.action("open_subscription_permalink")(
    subscriptions_events.open_subscription_permalink
)

# 글쓰기 참여 신청
app.action("open_writing_participation_view")(open_writing_participation_view)
app.view("writing_participation_view")(submit_writing_participation_view)

event_descriptions = {
    "/제출": "글 제출 시작",
    "submit_view": "글 제출 완료",
    "intro_modal": "다른 유저의 자기소개 확인",
    # "forward_message": "다른 채널로 메시지 전송",
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
    "app_mention": "앱 멘션",
    "/예치금": "예치금 조회",
    "/제출내역": "제출내역 조회",
    "/관리자": "관리자 메뉴 조회",
    "/도움말": "도움말 조회",
    "coffee_chat_proof_message": "커피챗 인증 메시지",
    "cancel_coffee_chat_proof_button": "커피챗 인증 안내 닫기",
    "submit_coffee_chat_proof_button": "커피챗 인증 제출 시작",
    "submit_coffee_chat_proof_view": "커피챗 인증 제출 완료",
    "sync_store_select": "데이터 동기화",
    "invite_channel": "채널 초대",
    "invite_channel_view": "채널 초대 완료",
    "app_home_opened": "홈 탭 열림",
    "open_deposit_view": "예치금 조회",
    "open_submission_history_view": "제출내역 조회",
    "open_help_view": "도움말 조회",
    "open_point_history_view": "포인트 내역 조회",
    "open_point_guide_view": "포인트 가이드 조회",
    "send_paper_plane_message": "종이비행기 메시지 전송 시작",
    "open_paper_plane_url": "종이비행기 URL 열기",
    "open_paper_plane_guide_view": "종이비행기 가이드 조회",
    "open_coffee_chat_history_view": "커피챗 내역 조회",
    "download_point_history": "포인트 내역 다운로드",
    "download_coffee_chat_history": "커피챗 내역 다운로드",
    "download_submission_history": "제출내역 다운로드",
    "send_paper_plane_message_view": "종이비행기 메시지 전송 완료",
    "channel_created": "채널 생성",
    "/종이비행기": "종이비행기 모달 열기",
    "subscribe_member": "멤버 구독 완료",
    "open_subscribe_member_view": "멤버 구독 모달 열기",
    "open_subscription_permalink": "구독한 멤버의 새 글 보기",
    "unsubscribe_member": "멤버 구독 취소",
    "open_writing_participation_view": "글쓰기 참여 신청 모달 열기",
    "writing_participation_view": "글쓰기 참여 신청 완료",
}
