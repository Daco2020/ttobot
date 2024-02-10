from typing import Any
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str

    BOT_TOKEN: str
    APP_TOKEN: str

    SCOPE: list[str]
    JSON_KEYFILE_DICT: dict[str, Any]
    SPREAD_SHEETS_URL: str
    DEPOSIT_SHEETS_URL: str

    ADMIN_CHANNEL: str
    ADMIN_IDS: list[str]

    SUPPORT_CHANNEL: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()  # type: ignore
