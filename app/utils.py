import datetime
from zoneinfo import ZoneInfo


def now_dt() -> datetime.datetime:
    """한국의 현재시간 반환합니다."""
    return datetime.datetime.now(tz=ZoneInfo("Asia/Seoul"))


def now_dt_to_str() -> str:
    """현재시간을 구글시트에 맞도록 문자열로 반환합니다."""
    return datetime.datetime.strftime(now_dt(), "%Y-%m-%d %H:%M:%S")
