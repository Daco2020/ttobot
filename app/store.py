import asyncio
import csv
import os
from app.client import SpreadSheetClient
from app.logging import log_event
from app.models import Bookmark

queue_lock = asyncio.Lock()

content_upload_queue: list[list[str]] = []
bookmark_upload_queue: list[list[str]] = []
bookmark_update_queue: list[Bookmark] = []  # TODO: 추후 타입 수정 필요
user_update_queue: list[list[str]] = []
coffee_chat_proof_upload_queue: list[list[str]] = []
point_history_upload_queue: list[list[str]] = []
paper_plane_upload_queue: list[list[str]] = []


class Store:
    def __init__(self, client: SpreadSheetClient) -> None:
        self._client = client

    def pull_all(self) -> None:
        """데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("users", values=self._client.get_values("users"))
        self.write("contents", values=self._client.get_values("contents"))
        self.write("bookmark", values=self._client.get_values("bookmark"))
        self.write(
            "coffee_chat_proof", values=self._client.get_values("coffee_chat_proof")
        )
        self.write("point_histories", values=self._client.get_values("point_histories"))
        self.write("paper_plane", values=self._client.get_values("paper_plane"))

    def pull_users(self) -> None:
        """유저 데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("users", values=self._client.get_values("users"))

    def pull_contents(self) -> None:
        """콘텐츠 데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("contents", values=self._client.get_values("contents"))

    def pull_bookmark(self) -> None:
        """북마크 데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("bookmark", values=self._client.get_values("bookmark"))

    def pull_coffee_chat_proof(self) -> None:
        """커피챗 인증 데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write(
            "coffee_chat_proof", values=self._client.get_values("coffee_chat_proof")
        )

    def pull_point_histories(self) -> None:
        """포인트 내역 데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("point_histories", values=self._client.get_values("point_histories"))

    def pull_paper_plane(self) -> None:
        """종이비행기 데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("paper_plane", values=self._client.get_values("paper_plane"))

    def write(self, table_name: str, values: list[list[str]]) -> None:
        """데이터를 저장소에 저장합니다."""
        with open(f"store/{table_name}.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerows(values)

    def read(self, table_name: str) -> list[list[str]]:
        """저장소에서 데이터를 읽어옵니다."""
        with open(f"store/{table_name}.csv") as f:
            reader = csv.reader(f, quoting=csv.QUOTE_ALL)
            data = list(reader)
        return data

    def upload_all(self, table_name: str) -> None:
        """해당 테이블의 모든 데이터를 업로드합니다."""
        values = self.read(table_name)
        self._client.bulk_upload(table_name, values)

    async def upload_queue(self) -> None:
        """새로 추가된 queue 가 있다면 upload 합니다."""
        global content_upload_queue
        global bookmark_upload_queue
        global bookmark_update_queue
        global user_update_queue
        global coffee_chat_proof_upload_queue
        global point_history_upload_queue
        global paper_plane_upload_queue

        async with queue_lock:
            temp_content_upload_queue = list(content_upload_queue)
            if temp_content_upload_queue:
                await asyncio.to_thread(
                    self._client.bulk_upload,
                    "contents",
                    temp_content_upload_queue,
                )
                content_upload_queue = self.initial_queue(
                    queue=content_upload_queue,
                    temp_queue=temp_content_upload_queue,
                )
                log_event(
                    actor="system",
                    event="uploaded_contents",
                    type="content",
                    description=f"{len(temp_content_upload_queue)}개 콘텐츠 업로드",
                    body={
                        "temp_content_upload_queue": temp_content_upload_queue,
                        "content_upload_queue": content_upload_queue,  # 디버깅을 위해 추가
                    },
                )

            temp_bookmark_upload_queue = list(bookmark_upload_queue)
            if temp_bookmark_upload_queue:
                await asyncio.to_thread(
                    self._client.bulk_upload,
                    "bookmark",
                    temp_bookmark_upload_queue,
                )
                bookmark_upload_queue = self.initial_queue(
                    queue=bookmark_upload_queue,
                    temp_queue=temp_bookmark_upload_queue,
                )
                log_event(
                    actor="system",
                    event="uploaded_bookmarks",
                    type="content",
                    description=f"{len(temp_bookmark_upload_queue)}개 북마크 업로드",
                    body={"temp_bookmark_upload_queue": temp_bookmark_upload_queue},
                )

            temp_bookmark_update_queue = list(bookmark_update_queue)
            if temp_bookmark_update_queue:
                for bookmark in temp_bookmark_update_queue:
                    await asyncio.to_thread(
                        self._client.update,
                        "bookmark",
                        bookmark,
                    )
                bookmark_update_queue = self.initial_queue(
                    queue=bookmark_update_queue,
                    temp_queue=temp_bookmark_update_queue,
                )
                log_event(
                    actor="system",
                    event="updated_bookmarks",
                    type="content",
                    description=f"{len(temp_bookmark_update_queue)}개 북마크 업데이트",
                    body={"temp_bookmark_update_queue": temp_bookmark_update_queue},
                )

            temp_user_update_queue = list(user_update_queue)
            if temp_user_update_queue:
                for values in temp_user_update_queue:
                    await asyncio.to_thread(
                        self._client.update_user,
                        "users",
                        values,
                    )
                user_update_queue = self.initial_queue(
                    queue=user_update_queue,
                    temp_queue=temp_user_update_queue,
                )
                log_event(
                    actor="system",
                    event="updated_user_introduction",
                    type="user",
                    description=f"{len(temp_user_update_queue)}개 유저 자기소개 업데이트",
                    body={"temp_user_update_queue": temp_user_update_queue},
                )

            temp_coffee_chat_proof_upload_queue = list(coffee_chat_proof_upload_queue)
            if temp_coffee_chat_proof_upload_queue:
                await asyncio.to_thread(
                    self._client.bulk_upload,
                    "coffee_chat_proof",
                    temp_coffee_chat_proof_upload_queue,
                )
                coffee_chat_proof_upload_queue = self.initial_queue(
                    queue=coffee_chat_proof_upload_queue,
                    temp_queue=temp_coffee_chat_proof_upload_queue,
                )
                log_event(
                    actor="system",
                    event="uploaded_coffee_chat_proofs",
                    type="community",
                    description=f"{len(temp_coffee_chat_proof_upload_queue)}개 커피챗 인증 업로드",
                    body={
                        "temp_coffee_chat_proof_upload_queue": temp_coffee_chat_proof_upload_queue
                    },
                )

            temp_point_history_upload_queue = list(point_history_upload_queue)
            if temp_point_history_upload_queue:
                await asyncio.to_thread(
                    self._client.bulk_upload,
                    "point_histories",
                    temp_point_history_upload_queue,
                )
                point_history_upload_queue = self.initial_queue(
                    queue=point_history_upload_queue,
                    temp_queue=temp_point_history_upload_queue,
                )
                log_event(
                    actor="system",
                    event="uploaded_point_histories",
                    type="point",
                    description=f"{len(temp_point_history_upload_queue)}개 포인트 내역 업로드",
                    body={
                        "temp_point_history_upload_queue": temp_point_history_upload_queue
                    },
                )

            temp_paper_plane_upload_queue = list(paper_plane_upload_queue)
            if temp_paper_plane_upload_queue:
                await asyncio.to_thread(
                    self._client.bulk_upload,
                    "paper_plane",
                    temp_paper_plane_upload_queue,
                )
                paper_plane_upload_queue = self.initial_queue(
                    queue=paper_plane_upload_queue,
                    temp_queue=temp_paper_plane_upload_queue,
                )
                log_event(
                    actor="system",
                    event="uploaded_paper_plane",
                    type="community",
                    description=f"{len(temp_paper_plane_upload_queue)}개 종이비행기 업로드",
                    body={
                        "temp_paper_plane_upload_queue": temp_paper_plane_upload_queue
                    },
                )

    def backup(self, table_name: str) -> None:
        values = self.read(table_name)
        self._client.backup(values)

    def initialize_logs(self) -> None:
        """로그를 초기화합니다."""
        open("store/logs.csv", "w").close()

    def initial_queue(self, *, queue: list, temp_queue: list) -> list:
        """queue 에서 temp_queue 를 제거한 값을 반환합니다."""
        return [entry for entry in queue if entry not in temp_queue]
