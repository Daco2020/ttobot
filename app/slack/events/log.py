from datetime import datetime

from app.bigquery.queue import CommentDataType, EmojiDataType, PostDataType
from app.slack.types import MessageBodyType, ReactionBodyType
from app.bigquery import queue as bigquery_queue
from slack_bolt.async_app import AsyncAck
from slack_sdk.web.async_client import AsyncWebClient


async def handle_comment_data(body: MessageBodyType) -> None:
    user = body["event"].get("user")
    if not user:
        print(user)
    else:
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

    # 공지사항을 이모지로 확인하면 포인트를 지급합니다. # TODO: 멤버 등록 후 활성화 필요
    # if (
    #     body["event"]["item"]["channel"] == settings.NOTICE_CHANNEL
    #     and body["event"]["reaction"] == "white_check_mark"
    # ):
    # text = point_service.grant_if_notice_emoji_checked(
    #     user_id=body["event"]["user"]
    # )
    # await client.chat_postMessage(channel=body["event"]["user"], text=text)
    # log_event(
    #     actor=body["event"]["user"],
    #     event="checked_notice",
    #     type=body["event"]["type"],
    #     description="공지사항 확인",
    #     body=body,
    # )
    # return


async def handle_reaction_removed(
    ack: AsyncAck,
    body: ReactionBodyType,
):
    """리액션 삭제 이벤트를 처리합니다."""
    await ack()
