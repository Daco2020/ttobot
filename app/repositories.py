from functools import reduce
from app import models
import polars as pl

from app.constants import ArchiveMessageSortEnum
from app.utils import remove_emoji


# TODO: 추후 레포지토리를 도메인별로 분리 필요
class MessageRepository:
    def __init__(self) -> None: ...

    def fetch_trigger_messages(
        self,
        offset: int = 0,
        limit: int = 10,
        user_id: str | None = None,
        search_word: str | None = None,
        descending: bool = True,
    ) -> list[models.TriggerMessage]:
        """조건에 맞는 트리거 메시지를 조회합니다."""
        df = pl.read_csv("store/trigger_message.csv")

        queries = []
        if user_id is not None:
            queries.append(pl.col("user_id") == user_id)
        if search_word is not None:
            queries.append(search_word in pl.col("trigger_word"))

        if queries:
            df = df.filter(pl.fold(queries, lambda a, b: a & b))

        df = df.sort("created_at", descending=descending)
        df = df.slice(offset, limit)

        return [models.TriggerMessage(**row) for row in df.to_dicts()]

    def fetch_archive_messages(
        self,
        offset: int = 0,
        limit: int = 10,
        ts: str | None = None,
        user_id: str | None = None,
        search_word: str | None = None,
        trigger_word: str | None = None,
        order_by: ArchiveMessageSortEnum = ArchiveMessageSortEnum.TS,
        descending: bool = True,
        exclude_emoji: bool = True,
    ) -> list[models.ArchiveMessage]:
        """조건에 맞는 아카이브 메시지를 조회합니다."""
        df = pl.read_csv("store/archive_message.csv")

        queries = []
        if ts is not None:
            queries.append(pl.col("ts").cast(str) == ts)
        if trigger_word is not None:
            queries.append(pl.col("trigger_word") == trigger_word)
        if user_id is not None:
            queries.append(pl.col("user_id") == user_id)
        if search_word is not None:
            queries.append(pl.col("message").str.contains(search_word))
        if queries:
            combined_condition = reduce(lambda a, b: a & b, queries)
            df = df.filter(combined_condition)

        if order_by is not None:
            df = df.sort(order_by, descending=descending)

        df = df.slice(offset, limit)

        return [
            models.ArchiveMessage(
                ts=row["ts"],
                channel_id=row["channel_id"],
                trigger_word=row["trigger_word"],
                user_id=row["user_id"],
                message=(
                    remove_emoji(row["message"]) if exclude_emoji else row["message"]
                ),
                file_urls=row["file_urls"],
                updated_at=row["updated_at"],
            )
            for row in df.to_dicts()
        ]
