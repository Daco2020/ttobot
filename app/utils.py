import regex as re
import datetime

from zoneinfo import ZoneInfo

import googletrans


def tz_now(tz: str = "Asia/Seoul") -> datetime.datetime:
    """현재시간 반환합니다."""
    return datetime.datetime.now(tz=ZoneInfo(tz))


def tz_now_to_str(tz: str = "Asia/Seoul") -> str:
    """현재시간을 문자열로 반환합니다."""
    return datetime.datetime.strftime(tz_now(tz), "%Y-%m-%d %H:%M:%S")


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
