import csv
import os
from app.client import SpreadSheetClient
from app.logging import log_event
from app.models import Bookmark

content_upload_queue: list[list[str]] = []
bookmark_upload_queue: list[list[str]] = []
bookmark_update_queue: list[Bookmark] = []  # TODO: 추후 타입 수정 필요
user_update_queue: list[list[str]] = []
trigger_message_upload_queue: list[list[str]] = []
archive_message_upload_queue: list[list[str]] = []
archive_message_update_queue: list[list[str]] = []


class Store:
    def __init__(self, client: SpreadSheetClient) -> None:
        self._client = client

    def pull(self) -> None:
        """데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("users", values=self._client.get_values("users"))
        self.write("contents", values=self._client.get_values("contents"))
        self.write("bookmark", values=self._client.get_values("bookmark"))
        self.write("trigger_message", values=self._client.get_values("trigger_message"))
        self.write("archive_message", values=self._client.get_values("archive_message"))

    def write(self, table_name: str, values: list[list[str]]) -> None:
        with open(f"store/{table_name}.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerows(values)

    def read(self, table_name: str) -> list[list[str]]:
        with open(f"store/{table_name}.csv") as f:
            reader = csv.reader(f, quoting=csv.QUOTE_ALL)
            data = list(reader)
        return data

    def upload(self, table_name: str) -> None:
        values = self.read(table_name)
        self._client.upload(table_name, values)

    def upload_queue(self, contents: str = "contents") -> None:
        """새로 추가된 queue 가 있다면 upload 합니다."""
        global content_upload_queue
        if content_upload_queue:
            self._client.upload(contents, content_upload_queue)
            log_event(
                actor="system",
                event="uploaded_contents",
                type="content",
                description=f"{len(content_upload_queue)}개 콘텐츠 업로드",
                body={"content_upload_queue": content_upload_queue},
            )
            content_upload_queue = []

        global bookmark_upload_queue
        if bookmark_upload_queue:
            self._client.upload("bookmark", bookmark_upload_queue)
            log_event(
                actor="system",
                event="uploaded_bookmarks",
                type="content",
                description=f"{len(bookmark_upload_queue)}개 북마크 업로드",
                body={"bookmark_upload_queue": bookmark_upload_queue},
            )
            bookmark_upload_queue = []

        global bookmark_update_queue
        if bookmark_update_queue:
            for bookmark in bookmark_update_queue:
                self._client.update(sheet_name="bookmark", obj=bookmark)
            log_event(
                actor="system",
                event="updated_bookmarks",
                type="content",
                description=f"{len(bookmark_update_queue)}개 북마크 업데이트",
                body={"bookmark_update_queue": bookmark_update_queue},
            )
            bookmark_update_queue = []

        global user_update_queue
        if user_update_queue:
            for values in user_update_queue:
                self._client.update_user(sheet_name="users", values=values)
            log_event(
                actor="system",
                event="updated_user_introduction",
                type="user",
                description=f"{len(user_update_queue)}개 유저 자기소개 업데이트",
                body={"user_update_queue": user_update_queue},
            )
            user_update_queue = []

        global trigger_message_upload_queue
        if trigger_message_upload_queue:
            self._client.upload("trigger_message", trigger_message_upload_queue)
            log_event(
                actor="system",
                event="uploaded_trigger_message",
                type="community",
                description=f"{len(trigger_message_upload_queue)}개 키워드 메시지 업로드",
                body={"trigger_message_upload_queue": trigger_message_upload_queue},
            )
            trigger_message_upload_queue = []

        global archive_message_upload_queue
        if archive_message_upload_queue:
            self._client.upload("archive_message", archive_message_upload_queue)
            log_event(
                actor="system",
                event="uploaded_archive_message",
                type="community",
                description=f"{len(archive_message_upload_queue)}개 아카이브 메시지 업로드",
                body={"archive_message_upload_queue": archive_message_upload_queue},
            )
            archive_message_upload_queue = []

        global archive_message_update_queue
        if archive_message_update_queue:
            for values in archive_message_update_queue:
                self._client.update_archive_message(
                    sheet_name="archive_message", values=values
                )
            log_event(
                actor="system",
                event="updated_archive_message",
                type="user",
                description=f"{len(archive_message_update_queue)}개 아카이브 메시지 업데이트",
                body={"archive_message_update_queue": archive_message_update_queue},
            )
            archive_message_update_queue = []

    def backup(self, table_name: str) -> None:
        values = self.read(table_name)
        self._client.backup(values)

    def initialize_logs(self) -> None:
        open("store/logs.csv", "w").close()
