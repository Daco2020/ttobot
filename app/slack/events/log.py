import csv
from datetime import datetime
import os

from app.bigquery.queue import CommentDataType, EmojiDataType, PostDataType
from app.logging import log_event
from app.slack.repositories import SlackRepository
from app.slack.services.point import PointService
from app.slack.types import MessageBodyType, ReactionBodyType
from app.bigquery import queue as bigquery_queue
from app.config import settings
from slack_bolt.async_app import AsyncAck
from slack_sdk.web.async_client import AsyncWebClient

from app.utils import tz_now_to_str


async def handle_comment_data(body: MessageBodyType) -> None:
    data = CommentDataType(
        user_id=body["event"]["user"],
        channel_id=body["event"]["channel"],
        ts=body["event"]["thread_ts"],  # type: ignore
        comment_ts=body["event"]["ts"],
        tddate=datetime.fromtimestamp(float(body["event"]["ts"])).date(),
        createtime=datetime.fromtimestamp(float(body["event"]["ts"])),
        text=body["event"]["text"],
    )
    bigquery_queue.comments_upload_queue.append(data)


async def handle_post_data(body: MessageBodyType) -> None:
    data = PostDataType(
        user_id=body["event"]["user"],
        channel_id=body["event"]["channel"],
        ts=body["event"]["ts"],
        tddate=datetime.fromtimestamp(float(body["event"]["ts"])).date(),
        createtime=datetime.fromtimestamp(float(body["event"]["ts"])),
        text=body["event"]["text"],
    )
    bigquery_queue.posts_upload_queue.append(data)


async def handle_reaction_added(
    ack: AsyncAck,
    body: ReactionBodyType,
    client: AsyncWebClient,
) -> None:
    """리액션 추가 이벤트를 처리합니다."""
    await ack()

    data = EmojiDataType(
        user_id=body["event"]["user"],
        channel_id=body["event"]["item"]["channel"],
        ts=body["event"]["item"]["ts"],
        reactions_ts=body["event"]["event_ts"],
        tddate=datetime.fromtimestamp(float(body["event"]["event_ts"])).date(),
        createtime=datetime.fromtimestamp(float(body["event"]["event_ts"])),
        reaction=body["event"]["reaction"],
    )
    bigquery_queue.emojis_upload_queue.append(data)

    # 공지사항을 이모지로 확인하면 포인트를 지급합니다.
    if (
        body["event"]["item"]["channel"] == settings.NOTICE_CHANNEL
        and body["event"]["reaction"] == "noti-check"
    ):
        channel_id = body["event"]["item"]["channel"]
        ts = body["event"]["item"]["ts"]

        if await _is_thread_message(
            client=client,
            channel_id=channel_id,
            ts=ts,
        ):
            return

        user_id = body["event"]["user"]
        notice_ts = body["event"]["item"]["ts"]

        if _is_checked_notice(user_id, notice_ts):
            return

        point_service = PointService(repo=SlackRepository())
        text = point_service.grant_if_notice_emoji_checked(user_id=user_id)
        await client.chat_postMessage(channel=user_id, text=text)

        _write_checked_notice(user_id, notice_ts)

        log_event(
            actor=user_id,
            event="checked_notice",
            type=body["event"]["type"],
            description="공지사항 확인",
            body=body,
        )
        return


async def _is_thread_message(client: AsyncWebClient, channel_id: str, ts: str) -> bool:
    """메시지가 스레드 메시지인지 확인합니다."""
    res = await client.conversations_replies(channel=channel_id, ts=ts)

    messages: list[dict] = res.get("messages", [])
    if messages and messages[0].get("thread_ts"):
        # thread_ts 키가 있으면 스레드 메시지입니다.
        return True

    return False


def _is_checked_notice(user_id: str, notice_ts: str) -> bool:
    """이전에 공지를 확인한 적이 있는지 확인합니다."""
    file_path = "store/_checked_notice.csv"
    file_exists = os.path.isfile(file_path)

    if file_exists:
        with open(file_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["user_id"] == user_id and row["notice_ts"] == notice_ts:
                    return True

    return False


def _write_checked_notice(user_id: str, notice_ts: str) -> None:
    """공지 확인 기록을 저장합니다."""
    # 공지 확인 기록은 스프레드시트에 업로드 하지 않습니다. 이 경우 파일명 앞에 _를 붙입니다.
    file_path = "store/_checked_notice.csv"
    file_exists = os.path.isfile(file_path)

    with open(file_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["user_id", "notice_ts", "created_at"],
            quoting=csv.QUOTE_ALL,
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(
            {
                "user_id": user_id,
                "notice_ts": notice_ts,
                "created_at": tz_now_to_str(),
            }
        )


async def handle_reaction_removed(
    ack: AsyncAck,
    body: ReactionBodyType,
):
    """리액션 삭제 이벤트를 처리합니다."""
    await ack()
