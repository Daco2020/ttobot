import datetime
from zoneinfo import ZoneInfo


def now_dt() -> datetime.datetime:
    """한국의 현재시간 반환합니다."""
    return datetime.datetime.now(tz=ZoneInfo("Asia/Seoul"))


def print_log(*args) -> None:
    print("------")
    print("time:", now_dt())
    print("message:", *args)
    print("------")
