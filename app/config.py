import datetime
from typing import Any
from pydantic import BaseSettings


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


# constants
URL_REGEX = r"((http|https):\/\/)?[a-zA-Z0-9.-]+(\.[a-zA-Z]{2,})"
MAX_PASS_COUNT = 2
DUE_DATES = [
    datetime.datetime(2023, 12, 10).date(),  # 1회차
    datetime.datetime(2023, 12, 24).date(),  # 2회차
    datetime.datetime(2024, 1, 7).date(),  # 3회차
    datetime.datetime(2024, 1, 21).date(),  # 4회차
    datetime.datetime(2024, 2, 4).date(),  # 5회차
    datetime.datetime(2024, 2, 18).date(),  # 6회차
    datetime.datetime(2024, 3, 3).date(),  # 7회차
    datetime.datetime(2024, 3, 17).date(),  # 8회차
    datetime.datetime(2024, 3, 31).date(),  # 9회차
    datetime.datetime(2024, 4, 14).date(),  # 10회차 - 글또 9기 종료
    datetime.datetime(2024, 4, 28).date(),  # 11회차
    datetime.datetime(2024, 5, 12).date(),  # 12회차
    datetime.datetime(2024, 5, 26).date(),  # 13회차
    datetime.datetime(2024, 6, 9).date(),  # 14회차
    datetime.datetime(2024, 6, 23).date(),  # 15회차
]
