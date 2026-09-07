from typing import Any
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str
    SERVER_DOMAIN: str
    CLIENT_DOMAIN: str

    SLACK_BOT_TOKEN: str
    SLACK_APP_TOKEN: str
    SLACK_CLIENT_ID: str
    SLACK_CLIENT_SECRET: str

    SCOPE: list[str]
    JSON_KEYFILE_DICT: dict[str, Any]
    SPREAD_SHEETS_URL: str
    DEPOSIT_SHEETS_URL: str
    SECRET_KEY: str
    BIGQUERY_CREDENTIALS: dict[str, Any]
    BIGQUERY_DATABASE_ID: str

    NOTICE_CHANNEL: str
    BOT_SUPPORT_CHANNEL: str
    SUPPORT_CHANNEL: str
    THANKS_CHANNEL: str
    COFFEE_CHAT_PROOF_CHANNEL: str
    ADMIN_CHANNEL: str
    WRITING_CHANNEL: str
    ADMIN_IDS: list[str]
    TTOBOT_USER_ID: str
    SUPER_ADMIN: str

    # self-ping 대상 공개 URL (https:// 포함). 비어 있으면 self-ping 비활성.
    # Koyeb 무료 인스턴스의 1시간 유휴 scale-to-zero 를 막기 위해 5분마다 GET 한다.
    KOYEB_URL: str = ""

    POINT_MAP: dict[str, Any]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
