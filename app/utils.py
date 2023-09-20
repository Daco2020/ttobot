import datetime
from functools import wraps
import re
from zoneinfo import ZoneInfo
import inspect


def now_dt() -> datetime.datetime:
    """한국의 현재시간 반환합니다."""
    return datetime.datetime.now(tz=ZoneInfo("Asia/Seoul"))


def now_dt_to_str() -> str:
    """현재시간을 구글시트에 맞도록 문자열로 반환합니다."""
    return datetime.datetime.strftime(now_dt(), "%Y-%m-%d %H:%M:%S")


def print_log(*args) -> None:
    info = re.sub(" +", " ", " ".join(args).replace("\n", " ").replace(",", " "))
    log = f"{now_dt()} - - INFO: {info}"
    print(log)
    with open("store/logs.csv", "a") as f:
        f.write(f"{log}\n")


def my_decorator(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        print(args)
        print(kwargs)
        await func(*args, **kwargs)

    return wrapper


def _start_log(body: dict[str, str], type: str) -> str:
    return f"{body.get('user_id')}({body.get('channel_id')}) 님이 {type} 를 시작합니다."


def 현재_함수명_출력():
    현재_함수명 = inspect.currentframe().f_code.co_name
    print(f"현재 함수의 이름은 '{현재_함수명}'이야")


현재_함수명_출력()
