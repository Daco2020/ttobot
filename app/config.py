import datetime
from pydantic import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    APP_TOKEN: str

    SCOPE: list
    JSON_KEYFILE_DICT: dict
    SPREAD_SHEETS_URL: str
    DEPOSIT_SHEETS_URL: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


# sheet constants
RAW_DATA_SHEET = "raw_data"
USERS_SHEET = "users"
LOG_SHEET = "log"
BACKUP_SHEET = "backup"

# views constants
SUBMIT_VIEW = "submit_view"
PASS_VIEW = "pass_view"
SEARCH_VIEW = "search_view"

# constants
URL_REGEX = r"((http|https):\/\/)?[a-zA-Z0-9.-]+(\.[a-zA-Z]{2,})"
MAX_PASS_COUNT = 2
DUE_DATES = [
    datetime.datetime(2023, 2, 12).date(),
    datetime.datetime(2023, 2, 26).date(),
    datetime.datetime(2023, 3, 12).date(),
    datetime.datetime(2023, 3, 26).date(),
    datetime.datetime(2023, 4, 9).date(),
    datetime.datetime(2023, 4, 23).date(),
    datetime.datetime(2023, 5, 7).date(),
    datetime.datetime(2023, 5, 21).date(),
    datetime.datetime(2023, 6, 4).date(),
    datetime.datetime(2023, 6, 18).date(),
    datetime.datetime(2023, 7, 2).date(),
    datetime.datetime(2023, 7, 16).date(),  # 글또 8기 12회차 종료
    datetime.datetime(2023, 7, 30).date(),
    datetime.datetime(2023, 8, 13).date(),
    datetime.datetime(2023, 8, 27).date(),
    datetime.datetime(2023, 9, 10).date(),
    datetime.datetime(2023, 9, 24).date(),
    datetime.datetime(2023, 10, 8).date(),
]
