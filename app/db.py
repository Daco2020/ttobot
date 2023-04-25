import os
from app.client import SpreadSheetClient


def fetch_db(client: SpreadSheetClient) -> None:
    """서버 저장소를 동기화합니다."""
    create_db_path()
    client.fetch_users()
    client.fetch_contents()


def create_db_path():
    try:
        os.mkdir("db")
    except FileExistsError:
        pass


def create_log_file(client: SpreadSheetClient) -> None:
    """로그파일을 초기화 및 생성합니다."""
    client.create_log_file()


def upload_logs(client: SpreadSheetClient) -> None:
    """로그를 업로드합니다."""
    client.upload_logs()
