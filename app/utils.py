import datetime
from zoneinfo import ZoneInfo


def now_dt(tz: str = "Asia/Seoul") -> datetime.datetime:
    """현재시간 반환합니다."""
    return datetime.datetime.now(tz=ZoneInfo(tz))


def now_dt_to_str(tz: str = "Asia/Seoul") -> str:
    """현재시간을 문자열로 반환합니다."""
    return datetime.datetime.strftime(now_dt(tz), "%Y-%m-%d %H:%M:%S")
