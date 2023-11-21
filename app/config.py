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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()  # type: ignore


# constants
URL_REGEX = r"((http|https):\/\/)?[a-zA-Z0-9.-]+(\.[a-zA-Z]{2,})"
MAX_PASS_COUNT = 2
DUE_DATES = [  # TODO: 환경변수로 변경하기
    datetime.datetime(2023, 7, 16).date(),  # 글또 8기 12회차 종료
    datetime.datetime(2023, 7, 30).date(),
    datetime.datetime(2023, 8, 13).date(),
    datetime.datetime(2023, 8, 27).date(),
    datetime.datetime(2023, 9, 10).date(),
    datetime.datetime(2023, 9, 24).date(),
    datetime.datetime(2023, 10, 8).date(),
    datetime.datetime(2023, 10, 22).date(),
    datetime.datetime(2023, 11, 5).date(),
    datetime.datetime(2023, 11, 12).date(),
    datetime.datetime(2023, 11, 26).date(),
    datetime.datetime(2023, 12, 10).date(),
]
