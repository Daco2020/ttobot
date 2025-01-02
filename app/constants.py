import datetime
from enum import Enum


URL_REGEX = r"((http|https):\/\/)?[a-zA-Z0-9.-]+(\.[a-zA-Z]{2,})"
MAX_PASS_COUNT = 2
DUE_DATES = [  # 글또 시작일 을 포함한 오름차순 마감일 리스트
    datetime.datetime(2024, 9, 29).date(),  # 0회차 - 글또 10기 시작
    datetime.datetime(2024, 10, 13).date(),  # 1회차
    datetime.datetime(2024, 10, 27).date(),  # 2회차
    datetime.datetime(2024, 11, 10).date(),  # 3회차
    datetime.datetime(2024, 11, 24).date(),  # 4회차
    # datetime.datetime(2024, 12, 8).date(),  # 비상계엄으로 인한 2주 연장
    datetime.datetime(2024, 12, 22).date(),  # 5회차
    datetime.datetime(2025, 1, 5).date(),  # 6회차
    datetime.datetime(2025, 1, 19).date(),  # 7회차
    datetime.datetime(2025, 2, 2).date(),  # 8회차
    datetime.datetime(2025, 2, 16).date(),  # 9회차
    datetime.datetime(2025, 3, 2).date(),  # 10회차
    datetime.datetime(2025, 3, 16).date(),  # 11회차
    datetime.datetime(2025, 3, 30).date(),  # 12회차
    datetime.datetime(2025, 4, 13).date(),  # 추가회차(임시)
]


class ContentCategoryEnum(str, Enum):
    CODETREE = "코드트리 x 글또 블로그 챌린지 2기"
    GILBUT = "길벗 책 리뷰"
    HANBIT = "한빛미디어 책 리뷰"
    PROJECT = "프로젝트"
    TECH = "기술 & 언어"
    CULTURE = "조직 & 문화"
    JOB = "취준 & 이직"
    DAILY = "일상 & 생각 & 회고"
    ETC = "기타"


class ContentSortEnum(str, Enum):
    DT = "dt"
    RELEVANCE = "relevance"
    # LIKE = "like" # TODO: 추후 추가하기


remind_message = """👋 안녕하세요! 오늘은 글 제출 마감일이에요.
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

# # 크리스마스 버전
# paper_plane_color_maps = [
#     {"color_label": "christmas_1", "bg_color": "#BC2026", "text_color": "#FFCCCC"},  # 불꽃 같은 빨간색
#     {"color_label": "christmas_2", "bg_color": "#118911", "text_color": "#E2FAE2"},  # 싱그러운 초록색
#     {"color_label": "christmas_3", "bg_color": "#EBB84E", "text_color": "#252525"},  # 맑은 하늘색
#     {"color_label": "christmas_4", "bg_color": "#DB7F3E", "text_color": "#F2DED0"},  # 밝은 금색
#     {"color_label": "christmas_5", "bg_color": "#74528F", "text_color": "#F5EBFC"},  # 진한 보라색
#     {"color_label": "christmas_6", "bg_color": "#874544", "text_color": "#F7E3E3"},  # 잘 익은 토마토색
# ]

# fmt: on


# 10기 1_채널 아이디 상수
PRIMARY_CHANNEL = [
    "C07P09BTQAW",  # 1_대나무숲_고민_공유
    "C07PXJR6KRP",  # 1_소모임_홍보
    "C07PD016V7T",  # 1_자료_공유
    "C07NKNYTFN3",  # 1_자유_홍보
    "C07P09N1XM0",  # 1_자유로운담소
    "C07PP3V0524",  # 1_큐레이션
    "C07PP3A5GGG",  # 1_온라인_모각글
    "C07NKNP2RSB",  # 1_자기소개
    "C07PG0G4RQD",  # 1_감사는_비행기를_타고
    "C07NTLWAWR4",  # 1_커피챗_또는_모임_후기
    "C07NKP4M69M",  # 1_커피챗_번개_모각글_하실_분
    "C05J87UPC3F",  # dev 채널 1 (로컬 테스트 채널)
    "C07PD0VMHJM",  # dev 채널 2 (또봇 크루 채널)
]


BOT_IDS = [
    "U07PJ6J7FFV",
    "U07P0BB4YKV",
    "U07PFJCHHFF",
    "U07PK8CLGKW",
    "U07P8E69V3N",
    "U07PB8HF4V8",
    "U07PAMU09AS",
    "U07PSF2PKKK",
    "U07PK195U74",
    "U04GVDM0R4Y",
    "USLACKBOT",
]
