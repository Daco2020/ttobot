import csv
import os
from app.client import SpreadSheetClient
from app.logging import log_event
from app.models import Bookmark

content_upload_queue: list[list[str]] = []
bookmark_upload_queue: list[list[str]] = []
bookmark_update_queue: list[Bookmark] = []  # TODO: 추후 타입 수정 필요


class Store:
    def __init__(self, client: SpreadSheetClient) -> None:
        self._client = client

    def sync(self) -> None:
        """데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("users", values=self._client.get_values("users"))
        self.write("contents", values=self._client.get_values("contents"))
        self.write("bookmark", values=self._client.get_values("bookmark"))

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

    def upload_queue(self) -> None:
        """새로 추가된 queue 가 있다면 upload 합니다."""
        global content_upload_queue
        if content_upload_queue:
            self._client.upload("contents", content_upload_queue)
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

    def backup(self, table_name: str) -> None:
        values = self.read(table_name)
        self._client.backup(table_name, values)

    def initialize_logs(self) -> None:
        open("store/logs.csv", "w").close()
