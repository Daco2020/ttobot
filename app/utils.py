import csv
import random
import string
from typing import Any
import orjson
import regex as re
import datetime

from zoneinfo import ZoneInfo

import googletrans
import resource
import sys


def tz_now(tz: str = "Asia/Seoul") -> datetime.datetime:
    """현재시간 반환합니다."""
    return datetime.datetime.now(tz=ZoneInfo(tz))


def tz_now_to_str(tz: str = "Asia/Seoul") -> str:
    """현재시간을 문자열로 반환합니다."""
    return datetime.datetime.strftime(tz_now(tz), "%Y-%m-%d %H:%M:%S")


def generate_unique_id() -> str:
    """고유한 ID를 생성합니다."""
    # 무작위 문자열 6자리 + 밀리 세컨즈(문자로 치환된)
    random_str = "".join(random.choices(string.ascii_letters + string.digits, k=6))
    return f"{random_str}{str(int(datetime.datetime.now().timestamp() * 1000))}"


def is_english(text):
    """영어인지 한글인지 판별합니다."""
    if re.match("^[a-zA-Z]+$", text):
        return True
    elif re.match("^[가-힣]+$", text):
        return False
    else:
        return None


def translate_keywords(keywords: list[str]) -> list[str]:
    """키워드를 번역합니다."""
    translator = googletrans.Translator()
    results = []
    for keyword in keywords:
        value = is_english(keyword)
        if value is True:
            # 영어 -> 한글 번역, 한글이 없는 단어는 그대로 영어가 나올 수 있음.
            results.append(translator.translate(keyword, dest="ko").text.lower())
        elif value is False:
            results.append(translator.translate(keyword, dest="en").text.lower())
        else:
            continue
    return results


def remove_emoji(message: str) -> str:
    """이모지를 제거합니다."""
    emoji_code_pattern = re.compile(r":[a-zA-Z0-9_\-]+:|:\p{Script=Hangul}+:")
    return emoji_code_pattern.sub(r"", message)


def slack_link_to_markdown(text):
    """Slack 링크를 마크다운 링크로 변환합니다."""
    pattern = re.compile(r"<(http[s]?://[^\|]+)\|([^\>]+)>")
    return pattern.sub(r"[\2](\1)", text)


def convert_user_id_to_name(message: str) -> str:
    """슬랙 메시지에서 user_id를 name으로 변경합니다."""
    with open("store/users.csv") as f:
        reader = csv.DictReader(f)
        user_dict = {row["user_id"]: row["name"] for row in reader}

    user_ids = re.findall("<@([A-Z0-9]+)>", message)

    for user_id in user_ids:
        name = user_dict.get(user_id, user_id)
        message = message.replace(f"<@{user_id}>", name)

    return message


def dict_to_json_str(data: dict[str, Any]) -> str:
    """dict를 json string으로 변환합니다."""
    return orjson.dumps(data).decode("utf-8")


def json_str_to_dict(data: str) -> dict[str, Any]:
    """json string을 dict로 변환합니다."""
    return orjson.loads(data)


KST = ZoneInfo("Asia/Seoul")


def ts_to_dt(ts: str) -> datetime.datetime:
    """슬랙 ts 를 KST 벽시계 naive datetime 으로 변환합니다.

    프로세스 TZ 와 무관하다. 옛 서버(KST)의 naive fromtimestamp 와 같은 값이고 UTC 컨테이너에서도
    날짜가 어긋나지 않는다. BigQuery DATETIME/DATE 와 strftime 호환을 위해 tzinfo 는 뗀다.
    """
    return datetime.datetime.fromtimestamp(float(ts), tz=KST).replace(tzinfo=None)


def process_rss_mb(status_path: str = "/proc/self/status") -> float:
    """이 프로세스가 실제로 쓰는 메모리(MB). 리눅스는 /proc 의 VmRSS, 없으면 rusage 로 잰다.

    Koyeb 메모리 그래프에는 커널 파일 캐시까지 섞여 있어 실제 사용량을 따로 남긴다 (worklog 025).
    """
    try:
        with open(status_path) as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass

    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # 리눅스는 kB, macOS 는 바이트로 준다.
    return usage / 1024**2 if sys.platform == "darwin" else usage / 1024
