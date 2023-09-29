import os
from app.client import SpreadSheetClient


def sync_store(client: SpreadSheetClient) -> None:
    """데이터를 가져와 서버 저장소를 덮어씁니다."""
    create_store_path()
    client.download_users()
    client.download_contents()
    client.download_bookmarks()


def create_store_path():
    """서버 저장소 경로를 생성합니다."""
    os.makedirs("store", exist_ok=True)
