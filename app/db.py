import os
from app.client import SpreadSheetClient


def sync_db(client: SpreadSheetClient) -> None:
    """서버 저장소를 동기화합니다."""
    create_db_path()
    client.sync_users()
    client.sync_contents()


def create_db_path():
    try:
        os.mkdir("db")
    except FileExistsError:
        pass
