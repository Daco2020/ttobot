import csv
from datetime import datetime
import os

from app.bigquery.queue import CommentDataType, EmojiDataType, PostDataType
from app.logging import log_event
from app.slack.repositories import SlackRepository
from app.slack.services.point import PointService, send_point_noti_message
from app.slack.types import MessageBodyType, ReactionBodyType
from app.bigquery import queue as bigquery_queue
from app.config import settings
from slack_bolt.async_app import AsyncAck
from slack_sdk.web.async_client import AsyncWebClient
from app.utils import tz_now_to_str
from aiocache import cached


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
        await send_point_noti_message(
            client=client,
            channel=user_id,
            text=text,
            notice_ts=notice_ts,
        )

        _write_checked_notice(user_id, notice_ts)

        log_event(
            actor=user_id,
            event="checked_notice",
            type=body["event"]["type"],
            description="공지사항 확인",
            body=body,
        )
        return


def _is_thread_message_cache_key_builder(func, *args, **kwargs):
    # `args`에서 `client`를 제외하고 `channel_id`와 `ts`만 사용해 키를 생성
    if "channel_id" in kwargs and "ts" in kwargs:
        channel_id = kwargs["channel_id"]
        ts = kwargs["ts"]
    else:
        # 위치 인자를 사용할 때 `args`에서 두 번째와 세 번째 인자 사용
        channel_id = args[1]
        ts = args[2]
    return f"{func.__name__}:{channel_id}:{ts}"


@cached(ttl=60, key_builder=_is_thread_message_cache_key_builder)
async def _is_thread_message(client: AsyncWebClient, channel_id: str, ts: str) -> bool:
    """
    메시지가 스레드 메시지인지 확인합니다.
    캐시를 사용하여 동일한 메시지에 대한 중복 요청을 방지합니다.
    캐시를 사용하는 이유는 슬랙 API의 제한 때문입니다.
    conversations_replies(Web API Tier 3): 50+ per minute limit
    """
    res = await client.conversations_replies(channel=channel_id, ts=ts)
    messages: list[dict] = res.get("messages", [])
    for message in messages:
        # 대상 메시지를 찾습니다.
        if message["ts"] == ts:
            thread_ts = message.get("thread_ts")

            # thread_ts 가 없다면 일반 메시지 입니다. 단, 댓글이 있다면 thread_ts 가 있습니다.
            if not thread_ts:
                return False

            # thread_ts 가 대상 ts 와 일치하면 스레드 메시지가 아닌 댓글이 있는 일반 메시지입니다.
            if thread_ts == ts:
                return False

            # thread_ts 가 대상 ts 와 일치하지 않으면 일반 메시지가 아닌 스레드 메시지입니다.
            else:
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
