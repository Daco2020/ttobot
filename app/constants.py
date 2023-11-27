import datetime
from app.config import settings


URL_REGEX = r"((http|https):\/\/)?[a-zA-Z0-9.-]+(\.[a-zA-Z]{2,})"
MAX_PASS_COUNT = 2
DUE_DATES = [
    datetime.datetime(2023, 12, 10).date(),  # 1회차
    datetime.datetime(2023, 12, 24).date(),  # 2회차
    datetime.datetime(2024, 1, 7).date(),  # 3회차
    datetime.datetime(2024, 1, 21).date(),  # 4회차
    datetime.datetime(2024, 2, 4).date(),  # 5회차
    datetime.datetime(2024, 2, 18).date(),  # 6회차
    datetime.datetime(2024, 3, 3).date(),  # 7회차
    datetime.datetime(2024, 3, 17).date(),  # 8회차
    datetime.datetime(2024, 3, 31).date(),  # 9회차
    datetime.datetime(2024, 4, 14).date(),  # 10회차 - 글또 9기 종료
    datetime.datetime(2024, 4, 28).date(),  # 11회차
    datetime.datetime(2024, 5, 12).date(),  # 12회차
    datetime.datetime(2024, 5, 26).date(),  # 13회차
    datetime.datetime(2024, 6, 9).date(),  # 14회차
    datetime.datetime(2024, 6, 23).date(),  # 15회차
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
