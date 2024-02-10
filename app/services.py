from app import models
from app.constants import ArchiveMessageSortEnum
from app.repositories import MessageRepository


class AppService:
    def __init__(self, message_repo: MessageRepository) -> None:
        self._message_repo = message_repo

    def fetch_trigger_messages(
        self,
        offset: int = 0,
        limit: int = 10,
        ts: str | None = None,
        user_id: str | None = None,
        search_word: str | None = None,
        descending: bool = True,
    ) -> list[models.TriggerMessage]:
        """조건에 맞는 트리거 메시지를 조회합니다."""
        return self._message_repo.fetch_trigger_messages(
            offset=offset,
            limit=limit,
            ts=ts,
            user_id=user_id,
            search_word=search_word,
            descending=descending,
        )

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
        return self._message_repo.fetch_archive_messages(
            offset=offset,
            limit=limit,
            ts=ts,
            user_id=user_id,
            search_word=search_word,
            trigger_word=trigger_word,
            order_by=order_by,
            descending=descending,
            exclude_emoji=exclude_emoji,
        )
