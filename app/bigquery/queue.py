import asyncio
from datetime import date, datetime
from typing import TypedDict

import pandas as pd

from app.bigquery.client import BigqueryClient, TableNameEnum
from app.logging import logger


class CommentDataType(TypedDict):
    user_id: str
    channel_id: str
    ts: str  # 상위 메시지 timestamp
    comment_ts: str  # 댓글 timestamp
    tddate: date
    createtime: datetime
    text: str


class EmojiDataType(TypedDict):
    user_id: str
    channel_id: str
    ts: str
    reactions_ts: str
    tddate: date
    createtime: datetime
    reaction: str


class PostDataType(TypedDict):
    user_id: str
    channel_id: str
    ts: str
    tddate: date
    createtime: datetime
    text: str


queue_lock = asyncio.Lock()

comments_upload_queue: list[CommentDataType] = []
emojis_upload_queue: list[EmojiDataType] = []
posts_upload_queue: list[PostDataType] = []


class BigqueryQueue:
    def __init__(self, client: BigqueryClient) -> None:
        self._client = client

    async def upload(self) -> None:
        global comments_upload_queue, emojis_upload_queue, posts_upload_queue

        async with queue_lock:
            # 댓글 로그 업로드
            temp_comments_queue = list(comments_upload_queue)
            if temp_comments_queue:
                try:
                    logger.info(f"BigQuery 댓글 로그 업로드 시작: {len(temp_comments_queue)}개")
                    await asyncio.to_thread(
                        self._client.update_table,
                        pd.DataFrame(temp_comments_queue),
                        TableNameEnum.COMMENTS_LOG,
                        "append",
                    )
                    comments_upload_queue = [
                        entry
                        for entry in comments_upload_queue
                        if entry not in temp_comments_queue
                    ]
                    logger.info(f"BigQuery 댓글 로그 업로드 완료: {len(temp_comments_queue)}개")
                except Exception as e:
                    logger.error(f"BigQuery 댓글 로그 업로드 실패: {str(e)}")
                    raise

            # 이모지 로그 업로드
            temp_emojis_queue = list(emojis_upload_queue)
            if temp_emojis_queue:
                try:
                    logger.info(f"BigQuery 이모지 로그 업로드 시작: {len(temp_emojis_queue)}개")
                    await asyncio.to_thread(
                        self._client.update_table,
                        pd.DataFrame(temp_emojis_queue),
                        TableNameEnum.EMOJIS_LOG,
                        "append",
                    )
                    emojis_upload_queue = [
                        entry
                        for entry in emojis_upload_queue
                        if entry not in temp_emojis_queue
                    ]
                    logger.info(f"BigQuery 이모지 로그 업로드 완료: {len(temp_emojis_queue)}개")
                except Exception as e:
                    logger.error(f"BigQuery 이모지 로그 업로드 실패: {str(e)}")
                    raise

            # 게시글 로그 업로드
            temp_posts_queue = list(posts_upload_queue)
            if temp_posts_queue:
                try:
                    logger.info(f"BigQuery 게시글 로그 업로드 시작: {len(temp_posts_queue)}개")
                    await asyncio.to_thread(
                        self._client.update_table,
                        pd.DataFrame(temp_posts_queue),
                        TableNameEnum.POSTS_LOG,
                        "append",
                    )
                    posts_upload_queue = [
                        entry
                        for entry in posts_upload_queue
                        if entry not in temp_posts_queue
                    ]
                    logger.info(f"BigQuery 게시글 로그 업로드 완료: {len(temp_posts_queue)}개")
                except Exception as e:
                    logger.error(f"BigQuery 게시글 로그 업로드 실패: {str(e)}")
                    raise
