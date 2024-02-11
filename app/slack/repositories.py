import csv
from typing import Any
import pandas as pd

from app import store
from app import models
from app.slack.exception import BotException
from app.utils import tz_now_to_str


class SlackRepository:
    def __init__(self) -> None: ...

    def get_user(self, user_id: str) -> models.User | None:
        """유저와 콘텐츠를 가져옵니다."""
        if user := self._get_user(user_id):
            user.contents = self._fetch_contents(user_id)
            return user
        return None

    def _get_user(self, user_id: str) -> models.User | None:
        """유저를 가져옵니다."""
        users = self._fetch_users()
        for user in users:
            if user["user_id"] == user_id:
                return models.User(**user)
        return None

    def _fetch_users(self) -> list[dict[str, Any]]:
        """모든 유저를 가져옵니다."""
        with open("store/users.csv") as f:
            reader = csv.DictReader(f)
            users = [dict(row) for row in reader]
            return users

    def _fetch_contents(self, user_id: str) -> list[models.Content]:
        """유저의 콘텐츠를 오름차순(날짜)으로 정렬하여 가져옵니다."""
        with open("store/contents.csv") as f:
            reader = csv.DictReader(f)
            contents = [
                models.Content(**content)
                for content in reader
                if content["user_id"] == user_id
            ]
            return sorted(contents, key=lambda content: content.dt_)

    def update(self, user: models.User) -> None:
        """유저의 콘텐츠를 업데이트합니다."""
        # TODO: upload 로 이름 변경 필요
        if not user.contents:
            raise BotException("업데이트 대상 content 가 없어요.")
        store.content_upload_queue.append(user.recent_content.to_list_for_sheet())
        with open("store/contents.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(user.recent_content.to_list_for_csv())

    def fetch_contents(self) -> list[models.Content]:
        """모든 콘텐츠를 가져옵니다."""
        with open("store/contents.csv") as f:
            reader = csv.DictReader(f)
            contents = [
                models.Content(**content)
                for content in reader
                if content["type"] == "submit"
            ]
            return sorted(contents, key=lambda content: content.dt_, reverse=True)

    def fetch_contents_by_keyword(self, keyword: str) -> list[models.Content]:
        """키워드가 포함된 콘텐츠를 가져옵니다."""
        with open("store/contents.csv") as f:
            reader = csv.DictReader(f)
            contents = [
                models.Content(**content)
                for content in reader
                if keyword.lower()
                in (content["title"] + content["description"] + content["tags"]).lower()
                and content["type"] == "submit"
            ]
            return sorted(contents, key=lambda content: content.dt_, reverse=True)

    def get_user_id_by_name(self, name: str) -> str | None:
        """이름으로 user_id를 가져옵니다."""
        with open("store/users.csv") as f:
            reader = csv.DictReader(f)
            matching_users = [user for user in reader if name in user["name"]]

        if len(matching_users) == 1:  # 이름 부분 일치가 하나인 경우에만 반환
            return matching_users[0]["user_id"]
        elif len(matching_users) > 1:
            for user in matching_users:
                if user["name"] == name:
                    return user["user_id"]
        return None

    def fetch_user_ids_by_name(self, name: str) -> list[str]:
        """이름으로 user_ids를 가져옵니다."""
        with open("store/users.csv") as f:
            reader = csv.DictReader(f)
            return [user["user_id"] for user in reader if name in user["name"]]

    def create_bookmark(self, bookmark: models.Bookmark) -> None:
        """북마크를 생성합니다."""
        with open("store/bookmark.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(bookmark.to_list_for_csv())

    def get_bookmark(
        self,
        user_id: str,
        content_id: str,
        status: models.BookmarkStatusEnum = models.BookmarkStatusEnum.ACTIVE,
    ) -> models.Bookmark | None:
        bookmarks = self.fetch_bookmarks(user_id, status)
        for bookmark in bookmarks:
            if bookmark.content_id == content_id:
                return bookmark
        return None

    def fetch_bookmarks(
        self,
        user_id: str,
        status: models.BookmarkStatusEnum = models.BookmarkStatusEnum.ACTIVE,
    ) -> list[models.Bookmark]:
        """유저의 삭제되지 않은 북마크를 내림차순으로 가져옵니다."""
        with open("store/bookmark.csv") as f:
            reader = csv.DictReader(f)
            bookmarks = [
                models.Bookmark(**bookmark)  # type: ignore
                for bookmark in reader
                if bookmark["user_id"] == user_id and bookmark["status"] == status
            ]

        return sorted(bookmarks, key=lambda bookmark: bookmark.created_at, reverse=True)

    def update_bookmark(
        self,
        content_id: str,
        new_note: str = "",
        new_status: models.BookmarkStatusEnum = models.BookmarkStatusEnum.ACTIVE,
    ) -> None:
        """북마크를 업데이트합니다."""
        df = pd.read_csv("store/bookmark.csv")

        if new_note:
            df.loc[df["content_id"] == content_id, "note"] = new_note
        if new_status:
            df.loc[df["content_id"] == content_id, "status"] = new_status
        if new_note or new_status:
            df.loc[df["content_id"] == content_id, "updated_at"] = tz_now_to_str()

        df.to_csv("store/bookmark.csv", index=False, quoting=csv.QUOTE_ALL)

    def update_user(
        self,
        user_id: str,
        new_intro: str,
    ) -> None:
        """유저 정보를 업데이트합니다."""
        df = pd.read_csv("store/users.csv")
        df.loc[df["user_id"] == user_id, "intro"] = new_intro
        df.to_csv("store/users.csv", index=False, quoting=csv.QUOTE_ALL)

        if user := self._get_user(user_id):
            store.user_update_queue.append(user.to_list_for_sheet())

    def create_trigger_message(
        self,
        trigger_message: models.TriggerMessage,
    ) -> None:
        """키워드 메시지를 생성합니다."""
        with open("store/trigger_message.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(trigger_message.to_list_for_csv())

    def fetch_trigger_messages(self) -> list[models.TriggerMessage]:
        """키워드 메시지를 조회합니다."""
        with open("store/trigger_message.csv") as f:
            reader = csv.DictReader(f)
            return [models.TriggerMessage(**row) for row in reader]

    def create_archive_message(
        self,
        archive_message: models.ArchiveMessage,
    ) -> None:
        """아카이브 메시지를 생성합니다."""
        with open("store/archive_message.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(archive_message.to_list_for_csv())

    def fetch_archive_messages(
        self,
        channel_id: str,
        trigger_word: str,
        user_id: str,
    ):
        """아카이브 메시지를 조회합니다."""
        with open("store/archive_message.csv") as f:
            reader = csv.DictReader(f)
            return [
                models.ArchiveMessage(**row)
                for row in reader
                if row["channel_id"] == channel_id
                and row["trigger_word"] == trigger_word
                and row["user_id"] == user_id
            ]

    def update_archive_message(
        self,
        ts: str,
        new_message: str,
    ) -> None:
        """아카이브 메시지를 업데이트합니다."""
        df = pd.read_csv("store/archive_message.csv")
        df.loc[df["ts"] == float(ts), "message"] = new_message
        df.loc[df["ts"] == float(ts), "updated_at"] = tz_now_to_str()
        df.to_csv("store/archive_message.csv", index=False, quoting=csv.QUOTE_ALL)

    def get_archive_message(
        self,
        ts: str,
    ) -> models.ArchiveMessage | None:
        """아카이브 메시지를 조회합니다."""
        with open("store/archive_message.csv") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["ts"] == ts:
                    return models.ArchiveMessage(**row)
            return None

    def create_feedback_request(
        self,
        feedback_request: models.FeedbackRequest,
    ) -> None:
        """피드백 요청을 생성합니다."""
        with open("store/feedback_request.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(feedback_request.to_list_for_csv())
