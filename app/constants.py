import datetime
from enum import Enum


URL_REGEX = r"((http|https):\/\/)?[a-zA-Z0-9.-]+(\.[a-zA-Z]{2,})"
MAX_PASS_COUNT = 2

# 회차 간격(2주). 마지막 하드코딩 마감일 이후는 이 간격으로 자동 생성된다.
DUE_DATE_INTERVAL = datetime.timedelta(days=14)

# 글또 시작일(0회차)을 포함한 "역사적" 마감일 앵커 리스트(오름차순).
# 여기에 손으로 미래 회차를 계속 추가할 필요는 없다. 마지막 마감일 이후의
# 추가 회차는 get_due_dates() 가 2주 간격으로 자동 생성한다.
# 단, 4→5회차 사이 28일 간격(비상계엄 2주 연장)처럼 규칙에서 벗어난
# 역사적 예외가 있으므로 이 앵커 리스트 자체는 보존한다.
BASE_DUE_DATES = [
    datetime.date(2024, 9, 29),  # 0회차 - 글또 10기 시작
    datetime.date(2024, 10, 13),  # 1회차
    datetime.date(2024, 10, 27),  # 2회차
    datetime.date(2024, 11, 10),  # 3회차
    datetime.date(2024, 11, 24),  # 4회차
    # datetime.date(2024, 12, 8),  # 비상계엄으로 인한 2주 연장
    datetime.date(2024, 12, 22),  # 5회차
    datetime.date(2025, 1, 5),  # 6회차
    datetime.date(2025, 1, 19),  # 7회차
    datetime.date(2025, 2, 2),  # 8회차
    datetime.date(2025, 2, 16),  # 9회차
    datetime.date(2025, 3, 2),  # 10회차
    datetime.date(2025, 3, 16),  # 11회차
    datetime.date(2025, 3, 30),  # 12회차
    datetime.date(2025, 4, 13),  # 추가회차(13회차)
    datetime.date(2025, 4, 27),  # 추가회차(14회차)
    datetime.date(2025, 5, 11),  # 추가회차(15회차)
    datetime.date(2025, 5, 25),  # 추가회차(16회차)
    datetime.date(2025, 6, 8),  # 추가회차(17회차)
    datetime.date(2025, 6, 22),  # 추가회차(18회차)
    datetime.date(2025, 7, 6),  # 추가회차(19회차)
    datetime.date(2025, 7, 20),  # 추가회차(20회차)
    datetime.date(2025, 8, 3),  # 추가회차(21회차)
    datetime.date(2025, 8, 17),  # 추가회차(22회차)
    datetime.date(2025, 8, 31),  # 추가회차(23회차)
    datetime.date(2025, 9, 14),  # 추가회차(24회차)
    datetime.date(2025, 9, 28),  # 추가회차(25회차)
    datetime.date(2025, 10, 12),  # 추가회차(26회차)
    datetime.date(2025, 10, 26),  # 추가회차(27회차)
    datetime.date(2025, 11, 9),  # 추가회차(28회차)
    datetime.date(2025, 11, 23),  # 추가회차(29회차)
    datetime.date(2025, 12, 7),  # 추가회차(30회차)
    datetime.date(2025, 12, 21),  # 추가회차(31회차)
    datetime.date(2026, 1, 4),  # 추가회차(32회차)
    datetime.date(2026, 1, 18),  # 추가회차(33회차)
    datetime.date(2026, 2, 1),  # 추가회차(34회차)
    datetime.date(2026, 2, 15),  # 추가회차(35회차)
    datetime.date(2026, 3, 1),  # 추가회차(36회차)
    datetime.date(2026, 3, 15),  # 추가회차(37회차)
    datetime.date(2026, 3, 29),  # 추가회차(38회차)
    datetime.date(2026, 4, 12),  # 추가회차(39회차)
    datetime.date(2026, 4, 26),  # 추가회차(40회차)
    datetime.date(2026, 5, 10),  # 추가회차(41회차)
    datetime.date(2026, 5, 24),  # 추가회차(42회차)
    datetime.date(2026, 6, 7),  # 추가회차(43회차)
    datetime.date(2026, 6, 21),  # 추가회차(44회차)
    datetime.date(2026, 7, 5),  # 추가회차(45회차)
]


def get_due_dates(reference_date: datetime.date) -> list[datetime.date]:
    """기준일(reference_date)을 덮을 때까지 2주 간격으로 확장한 마감일 리스트를 반환한다.

    - BASE_DUE_DATES(역사적 앵커)는 항상 그대로 앞부분에 보존된다.
    - 마지막 마감일이 기준일보다 이르면, 기준일 이상이 될 때까지 DUE_DATE_INTERVAL
      간격으로 회차를 자동 생성해 덧붙인다. (마감일을 손으로 추가할 필요가 없다.)
    - 기준일이 과거이거나 앵커 범위 안이면 확장 없이 BASE_DUE_DATES 를 그대로 돌려준다.

    순수 함수다: 인자로 받은 기준일에만 의존하며 BASE_DUE_DATES 원본을 변경하지 않는다.
    """
    due_dates = list(BASE_DUE_DATES)
    while due_dates[-1] < reference_date:
        due_dates.append(due_dates[-1] + DUE_DATE_INTERVAL)
    return due_dates


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

# paper_plane_color_maps = [
#     {"color_label": "fiery_red", "bg_color": "#FF4500", "text_color": "#FFFFFF"},  # 불꽃 같은 빨간색
#     {"color_label": "fresh_green", "bg_color": "#32CD32", "text_color": "#FFFFFF"},  # 싱그러운 초록색
#     {"color_label": "sky_blue", "bg_color": "#1E90FF", "text_color": "#FFFFFF"},  # 맑은 하늘색
#     {"color_label": "bright_gold", "bg_color": "#FFD700", "text_color": "#000000"},  # 밝은 금색
#     {"color_label": "deep_violet", "bg_color": "#8A2BE2", "text_color": "#FFFFFF"},  # 진한 보라색
#     {"color_label": "ripe_tomato", "bg_color": "#FF6347", "text_color": "#FFFFFF"},  # 잘 익은 토마토색
#     {"color_label": "cool_steelblue", "bg_color": "#4682B4", "text_color": "#FFFFFF"},  # 차가운 스틸블루
#     {"color_label": "soft_slateblue", "bg_color": "#6A5ACD", "text_color": "#FFFFFF"},  # 부드러운 슬레이트블루
#     {"color_label": "pastel_chartreuse", "bg_color": "#A9F2A5", "text_color": "#2F4F4F"},  # 파스텔 차트레즈
#     {"color_label": "vivid_deeppink", "bg_color": "#FF1493", "text_color": "#FFFFFF"},  # 선명한 딥핑크
#     {"color_label": "blush_rosybrown", "bg_color": "#BC8F8F", "text_color": "#FFFFFF"},  # 블러쉬 로지브라운
#     {"color_label": "peach_silver", "bg_color": "#FFDAB9", "text_color": "#8B4513"},  # 복숭아빛 실버
#     {"color_label": "muted_seagreen", "bg_color": "#8FBC8F", "text_color": "#FFFFFF"},  # 차분한 바다초록색
#     {"color_label": "soft_lightcoral", "bg_color": "#F08080", "text_color": "#FFFFFF"},  # 부드러운 라이트코랄
#     {"color_label": "lavender_gray", "bg_color": "#E6E6FA", "text_color": "#4B0082"},  # 라벤더 그레이
#     {"color_label": "sunset_orange", "bg_color": "#FF7F50", "text_color": "#FFFFFF"},  # 석양 오렌지
#     {"color_label": "ocean_teal", "bg_color": "#008080", "text_color": "#FFFFFF"},  # 바다 청록색
#     {"color_label": "midnight_blue", "bg_color": "#191970", "text_color": "#FFFFFF"},  # 자정의 파란색
#     {"color_label": "buttercup_yellow", "bg_color": "#FFDD44", "text_color": "#000000"},  # 버터컵 옐로우
#     {"color_label": "rosewood", "bg_color": "#65000B", "text_color": "#FFFFFF"}  # 로즈우드
# ]


# 발렌타인 버전
paper_plane_color_maps = [
    {"color_label": "valentine_1", "bg_color": "#BC2026", "text_color": "#EEE1E1"},
    {"color_label": "valentine_2", "bg_color": "#862A2A", "text_color": "#EEE1E1"},
    {"color_label": "valentine_3", "bg_color": "#2A1010", "text_color": "#EEE1E1"},
    {"color_label": "valentine_4", "bg_color": "#D48E52", "text_color": "#2C2424"},
    {"color_label": "valentine_5", "bg_color": "#774A23", "text_color": "#EEE1E1"},
    {"color_label": "valentine_6", "bg_color": "#291707", "text_color": "#EEE1E1"},
    {"color_label": "valentine_7", "bg_color": "#FFEBBD", "text_color": "#2C2424"},
    {"color_label": "valentine_8", "bg_color": "#F0C86D", "text_color": "#2C2424"},
    {"color_label": "valentine_9", "bg_color": "#DC9E0D", "text_color": "#2C2424"},
    {"color_label": "valentine_10", "bg_color": "#BCA0C3", "text_color": "#2C2424"},
    {"color_label": "valentine_11", "bg_color": "#7E5389", "text_color": "#EEE1E1"},
    {"color_label": "valentine_12", "bg_color": "#99A799", "text_color": "#E2FAE2"},
    {"color_label": "valentine_13", "bg_color": "#EAA4C8", "text_color": "#2C2424"},
    {"color_label": "valentine_14", "bg_color": "#C26D99", "text_color": "#EEE1E1"},
    {"color_label": "valentine_15", "bg_color": "#913263", "text_color": "#EEE1E1"},
    {"color_label": "valentine_16", "bg_color": "#FFB7CF", "text_color": "#EEE1E1"},
    {"color_label": "valentine_17", "bg_color": "#FF95AF", "text_color": "#2C2424"},
    {"color_label": "valentine_18", "bg_color": "#FF5680", "text_color": "#2C2424"},
    {"color_label": "valentine_19", "bg_color": "#80C4BC", "text_color": "#2C2424"},
    {"color_label": "valentine_20", "bg_color": "#49ABA0", "text_color": "#EEE1E1"},
    {"color_label": "valentine_21", "bg_color": "#1E7D72", "text_color": "#EEE1E1"},
    {"color_label": "valentine_22", "bg_color": "#17635A", "text_color": "#EEE1E1"},
    {"color_label": "valentine_23", "bg_color": "#223943", "text_color": "#EEE1E1"},
    {"color_label": "valentine_24", "bg_color": "#264A28", "text_color": "#EEE1E1"},
    {"color_label": "valentine_25", "bg_color": "#6F9370", "text_color": "#EEE1E1"},
    {"color_label": "valentine_26", "bg_color": "#2C612D", "text_color": "#EEE1E1"},
    {"color_label": "valentine_27", "bg_color": "#0C380D", "text_color": "#EEE1E1"}
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
    "C08BCU9C5BN",  # 1_글또_커피챗_조_공유
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
