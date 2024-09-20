from app import models
from app.slack.repositories import SlackRepository

from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class PointCategory(str, Enum):
    WRITING = "글쓰기"
    NETWORKING = "네트워크"
    USER_TO_USER = "유저 간"
    OTHER = "기타"


class PointHistory(BaseModel):
    id: str
    user_id: str
    sender_user_id: str | None
    reason: str
    point: int
    category: PointCategory
    created_at: datetime


# TODO: 주고 받기, 피드백 등은 구체화 후 추가 예정
# 동기
class PointReasonMap(Enum):
    글_제출_기본 = {"point": 100, "reason": "글 제출"}
    글_제출_추가 = {"point": 10, "reason": "추가 글 제출"}
    글_제출_콤보 = {"point": 10, "reason": "글 제출 콤보"}
    글_제출_3콤보_보너스 = {"point": 300, "reason": "글 제출 3콤보 보너스"}
    글_제출_6콤보_보너스 = {"point": 600, "reason": "글 제출 6콤보 보너스"}
    글_제출_9콤보_보너스 = {"point": 900, "reason": "글 제출 9콤보 보너스"}
    글_제출_코어채널_1등 = {"point": 50, "reason": "코어채널 글 제출 1등"}
    글_제출_코어채널_2등 = {"point": 30, "reason": "코어채널 글 제출 2등"}
    글_제출_코어채널_3등 = {"point": 20, "reason": "코어채널 글 제출 3등"}
    큐레이션_요청 = {"point": 10, "reason": "큐레이션 요청"}
    큐레이션_선정 = {"point": 10, "reason": "큐레이션 선정 축하 보너스"}
    커피챗_인증 = {"point": 50, "reason": "커피챗 인증"}
    빌리지_반상회_참여 = {"point": 50, "reason": "빌리지 반상회 참여 보너스"}
    공지사항_확인_이모지 = {"point": 10, "reason": "공지사항 확인"}
    자기소개_작성 = {"point": 100, "reason": "자기소개 작성 보너스"}

    def point(self):
        return self.value["point"]

    def reason(self):
        return self.value["reason"]


# # 사용 예시
# point_info = PointReasonMap.글_제출_기본
# point_value = point_info.count()
# reason_text = point_info.reason()

# print(f"포인트: {point_value}, 이유: {reason_text}")


class PointService:
    def __init__(self, repo: SlackRepository, user: models.User) -> None:
        self._repo = repo
        self._user = user
