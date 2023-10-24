import csv
import os
from app.client import SpreadSheetClient


class Store:
    def __init__(self, client: SpreadSheetClient) -> None:
        self._client = client

    def sync(self) -> None:
        """데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("users.csv", values=self._client.get_values("users"))
        self.write("contents.csv", values=self._client.get_values("raw_data"))
        self.write("bookmark.csv", values=self._client.get_values("bookmark"))

    def write(self, file_name: str, values: list[list[str]]) -> None:
        with open(f"store/{file_name}", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerows(values)

    def read(self, file_name: str) -> list[list[str]]:
        with open(f"store/{file_name}") as f:
            reader = csv.reader(f)
            data = list(reader)
        return data

    def upload(self, file_name: str) -> None:
        values = self.read(file_name)
        self._client.upload_logs(file_name, values)

    def backup(self, file_name: str) -> None:
        values = self.read(file_name)
        self._client.backup(values)

    def initialize_logs(self) -> None:
        self.write("logs.csv", values=[[]])
