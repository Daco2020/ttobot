import csv
import os
from app.client import SpreadSheetClient
from app.logging import log_event
from app.models import Bookmark

content_upload_queue: list[list[str]] = []
bookmark_upload_queue: list[list[str]] = []
bookmark_update_queue: list[Bookmark] = []  # TODO: 추후 타입 수정 필요
user_update_queue: list[list[str]] = []
coffee_chat_proof_upload_queue: list[list[str]] = []
reaction_upload_queue: list[list[str]] = []
point_history_upload_queue: list[list[str]] = []


class Store:
    def __init__(self, client: SpreadSheetClient) -> None:
        self._client = client

    def pull(self) -> None:
        """데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("users", values=self._client.get_values("users"))
        self.write("contents", values=self._client.get_values("contents"))
        self.write("bookmark", values=self._client.get_values("bookmark"))
        self.write(
            "coffee_chat_proof", values=self._client.get_values("coffee_chat_proof")
        )
        self.write("reactions", values=self._client.get_values("reactions"))
        self.write("point_histories", values=self._client.get_values("point_histories"))

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

    def bulk_upload(self, table_name: str) -> None:
        values = self.read(table_name)
        self._client.bulk_upload(table_name, values)

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

        global coffee_chat_proof_upload_queue
        if coffee_chat_proof_upload_queue:
            self._client.upload("coffee_chat_proof", coffee_chat_proof_upload_queue)
            log_event(
                actor="system",
                event="uploaded_coffee_chat_proofs",
                type="community",
                description=f"{len(coffee_chat_proof_upload_queue)}개 커피챗 인증 업로드",
                body={"coffee_chat_proof_upload_queue": coffee_chat_proof_upload_queue},
            )
            coffee_chat_proof_upload_queue = []

        global reaction_upload_queue
        if reaction_upload_queue:
            self._client.upload("reactions", reaction_upload_queue)
            log_event(
                actor="system",
                event="uploaded_reactions",
                type="community",
                description=f"{len(reaction_upload_queue)}개 리액션 업로드",
                body={"reaction_upload_queue": reaction_upload_queue},
            )
            reaction_upload_queue = []

        global point_history_upload_queue
        if point_history_upload_queue:
            self._client.upload("point_histories", point_history_upload_queue)
            log_event(
                actor="system",
                event="uploaded_point_histories",
                type="point",
                description=f"{len(point_history_upload_queue)}개 포인트 내역 업로드",
                body={"point_history_upload_queue": point_history_upload_queue},
            )
            point_history_upload_queue = []

    def backup(self, table_name: str) -> None:
        values = self.read(table_name)
        self._client.backup(values)

    def initialize_logs(self) -> None:
        """로그를 초기화합니다."""
        open("store/logs.csv", "w").close()
