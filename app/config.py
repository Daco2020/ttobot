import datetime
from typing import Any
from pydantic import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    APP_TOKEN: str

    SCOPE: list[str]
    JSON_KEYFILE_DICT: dict[str, Any]
    SPREAD_SHEETS_URL: str
    DEPOSIT_SHEETS_URL: str

    ENV: str
    ADMIN_CHANNEL: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()  # type: ignore


# sheet constants
RAW_DATA_SHEET = "raw_data"
USERS_SHEET = "users"
LOG_SHEET = "log"
BACKUP_SHEET = "backup"
BOOKMARK_SHEET = "bookmark"

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


ANIMAL_TYPE = dict(
    cat=dict(emoji="🐈", name="고양이", description="고양이는 여유롭게 일상을 즐겨요."),
    seaotter=dict(emoji="🦦", name="해달", description="해달은 기술과 도구에 관심이 많고 문제해결을 좋아해요."),
    beaver=dict(emoji="🦫", name="비버", description="비버는 명확한 목표와 함께 협업을 즐겨요."),
    elephant=dict(emoji="🐘", name="코끼리", description="코끼리는 커리어에 관심이 많고 자부심이 넘쳐요."),
    dog=dict(emoji="🐕", name="강아지", description="강아지는 조직문화에 관심이 많고 팀워크를 중요하게 여겨요."),
    turtle=dict(emoji="🐢", name="거북이", description="거북이는 한 발 늦게 들어왔지만 끝까지 포기하지 않아요."),
)
