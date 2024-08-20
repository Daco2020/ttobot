import datetime
from enum import Enum
from app.config import settings


URL_REGEX = r"((http|https):\/\/)?[a-zA-Z0-9.-]+(\.[a-zA-Z]{2,})"
MAX_PASS_COUNT = 2
DUE_DATES = [  # 글또 시작일 을 포함한 오름차순 마감일 리스트
    datetime.datetime(2024, 9, 29).date(),  # 0회차 - 글또 10기 시작
    datetime.datetime(2024, 10, 13).date(),  # 1회차
    datetime.datetime(2024, 10, 27).date(),  # 2회차
    datetime.datetime(2024, 11, 10).date(),  # 3회차
    datetime.datetime(2024, 11, 24).date(),  # 4회차
    datetime.datetime(2024, 12, 8).date(),  # 5회차
    datetime.datetime(2024, 12, 22).date(),  # 6회차
    datetime.datetime(2025, 1, 5).date(),  # 7회차
    datetime.datetime(2025, 1, 19).date(),  # 8회차
    datetime.datetime(2025, 2, 2).date(),  # 9회차
    datetime.datetime(2025, 2, 16).date(),  # 10회차
    datetime.datetime(2025, 3, 2).date(),  # 11회차
    datetime.datetime(2025, 3, 16).date(),  # 12회차
    datetime.datetime(2025, 3, 30).date(),  # 추가회차
]


HELP_TEXT = f"""
👋🏼 *반가워요!*

> 저는 글또 활동을 도와주는 또봇 이에요. 
> 여러분이 글로 더 많이 소통할 수 있도록 다양한 기능을 제공하고 있어요.

💬 *아래 명령어를 입력해보세요!*

> `/제출`
> 이번 회차의 글을 제출할 수 있어요.

> `/패스`
> 이번 회차의 글을 패스할 수 있어요.

> `/제출내역`
> 자신의 글 제출내역을 볼 수 있어요.

> `/검색`
> 다른 사람들의 글을 검색할 수 있어요.

> `/북마크`
> 북마크한 글을 볼 수 있어요.

> `/예치금`
> 현재 남은 예치금을 알려드려요.

> `/도움말`
> 또봇 사용법을 알려드려요.

> 이 외에 궁금한 사항이 있다면 <#{settings.SUPPORT_CHANNEL}> 채널로 문의해주세요! 🙌🏼
> 또봇 코드가 궁금하다면 👉🏼 *<https://github.com/Daco2020/ttobot|또봇 깃허브>* 로 놀러오세요~ 🤗
"""


class ContentCategoryEnum(str, Enum):
    PROJECT = "프로젝트"
    TECH = "기술 & 언어"
    CULTURE = "조직 & 문화"
    JOB = "취준 & 이직"
    DAILY = "일상 & 생각"
    ETC = "기타"


class ContentSortEnum(str, Enum):
    DT = "dt"
    RELEVANCE = "relevance"
    # LIKE = "like" # TODO: 추후 추가하기


remind_message = """오늘은 글또 제출 마감일이에요.
지난 2주 동안 배우고 경험한 것들을 자정까지 나눠주세요.
{user_name} 님의 이야기를 기다릴게요!🙂"""
