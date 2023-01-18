import datetime
from zoneinfo import ZoneInfo


def now_dt() -> datetime.datetime:
    """한국 현재시간 반환합니다."""
    return datetime.datetime.now(tz=ZoneInfo("Asia/Seoul"))
