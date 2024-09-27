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
    datetime.datetime(2025, 3, 30).date(),  # 추가회차(임시)
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


# fmt: off

paper_plane_color_maps = [
    {"color_label": "fiery_red", "bg_color": "#FF4500", "text_color": "#FFFFFF"},  # 불꽃 같은 빨간색
    {"color_label": "fresh_green", "bg_color": "#32CD32", "text_color": "#FFFFFF"},  # 싱그러운 초록색
    {"color_label": "sky_blue", "bg_color": "#1E90FF", "text_color": "#FFFFFF"},  # 맑은 하늘색
    {"color_label": "bright_gold", "bg_color": "#FFD700", "text_color": "#000000"},  # 밝은 금색
    {"color_label": "deep_violet", "bg_color": "#8A2BE2", "text_color": "#FFFFFF"},  # 진한 보라색
    {"color_label": "ripe_tomato", "bg_color": "#FF6347", "text_color": "#FFFFFF"},  # 잘 익은 토마토색
    {"color_label": "cool_steelblue", "bg_color": "#4682B4", "text_color": "#FFFFFF"},  # 차가운 스틸블루
    {"color_label": "soft_slateblue", "bg_color": "#6A5ACD", "text_color": "#FFFFFF"},  # 부드러운 슬레이트블루
    {"color_label": "pastel_chartreuse", "bg_color": "#A9F2A5", "text_color": "#2F4F4F"},  # 파스텔 차트레즈
    {"color_label": "vivid_deeppink", "bg_color": "#FF1493", "text_color": "#FFFFFF"},  # 선명한 딥핑크
    {"color_label": "blush_rosybrown", "bg_color": "#BC8F8F", "text_color": "#FFFFFF"},  # 블러쉬 로지브라운
    {"color_label": "peach_silver", "bg_color": "#FFDAB9", "text_color": "#8B4513"},  # 복숭아빛 실버
    {"color_label": "muted_seagreen", "bg_color": "#8FBC8F", "text_color": "#FFFFFF"},  # 차분한 바다초록색
    {"color_label": "soft_lightcoral", "bg_color": "#F08080", "text_color": "#FFFFFF"},  # 부드러운 라이트코랄
    {"color_label": "lavender_gray", "bg_color": "#E6E6FA", "text_color": "#4B0082"},  # 라벤더 그레이
    {"color_label": "sunset_orange", "bg_color": "#FF7F50", "text_color": "#FFFFFF"},  # 석양 오렌지
    {"color_label": "ocean_teal", "bg_color": "#008080", "text_color": "#FFFFFF"},  # 바다 청록색
    {"color_label": "midnight_blue", "bg_color": "#191970", "text_color": "#FFFFFF"},  # 자정의 파란색
    {"color_label": "buttercup_yellow", "bg_color": "#FFDD44", "text_color": "#000000"},  # 버터컵 옐로우
    {"color_label": "rosewood", "bg_color": "#65000B", "text_color": "#FFFFFF"}  # 로즈우드
]

# fmt: on
