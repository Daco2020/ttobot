import datetime
from zoneinfo import ZoneInfo


def tz_now(tz: str = "Asia/Seoul") -> datetime.datetime:
    """현재시간 반환합니다."""
    return datetime.datetime.now(tz=ZoneInfo(tz))


def tz_now_to_str(tz: str = "Asia/Seoul") -> str:
    """현재시간을 문자열로 반환합니다."""
    return datetime.datetime.strftime(tz_now(tz), "%Y-%m-%d %H:%M:%S")
