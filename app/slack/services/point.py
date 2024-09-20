from app.slack.repositories import SlackRepository
from slack_sdk.web.async_client import AsyncWebClient

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
    giver_user_id: str = ""
    reason: str
    point: int
    category: PointCategory
    created_at: datetime


# TODO: 주고 받기, 피드백 등은 구체화 후 추가 예정
# 동기부여와 자극을 주는 포인트는 공개 채널에 알림을 준다.
# 수동으로 받는 포인트는 디엠 으로 알림을 준다.
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
    커피챗_인증 = {"point": 50, "reason": "커피챗 인증"}
    공지사항_확인_이모지 = {"point": 10, "reason": "공지사항 확인"}
    큐레이션_요청 = {"point": 10, "reason": "큐레이션 요청"}
    큐레이션_선정 = {"point": 10, "reason": "큐레이션 선정 축하 보너스"}
    빌리지_반상회_참여 = {"point": 50, "reason": "빌리지 반상회 참여 보너스"}
    자기소개_작성 = {"point": 100, "reason": "자기소개 작성 보너스"}

    def point(self):
        return self.value["point"]

    def reason(self):
        return self.value["reason"]


class PointService:
    def __init__(self, repo: SlackRepository) -> None:
        self._repo = repo

    def grant_if_post_submitted(self, user_id: str):
        """글을 제출했다면 포인트를 지급합니다."""
        point_info = PointReasonMap.글_제출_기본

        self._repo.add_point(
            user_id=user_id,
            reason=point_info.reason(),
            point=point_info.point(),
            category=PointCategory.WRITING,
        )

        # user = self._repo.get_user(user_id)

        # TODO: 추가 예정
        # if 글을 추가로 제출한다면:
        # if 글을 콤보로 제출한다면: 공개 알림
        # if 글을 3,6,9콤보로 제출한다면: 공개 알림
        # if 코어채널 제출 순위: 공개 알림

    def grant_if_coffee_chat_verified(self, user_id: str, client: AsyncWebClient):
        """
        공개: 커피챗 인증을 한 경우 포인트를 지급합니다.
        공개채널에 알림을 줍니다.
        """
        point_info = PointReasonMap.커피챗_인증

        self._repo.add_point(
            user_id=user_id,
            reason=point_info.reason(),
            point=point_info.point(),
            category=PointCategory.NETWORKING,
        )

        # TODO: 추가 예정
        # client.chat_postMessage()

    def grant_if_notice_emoji_checked(self, user_id: str):
        """공지사항을 확인한 경우 포인트를 지급합니다."""
        # TODO: 공지사항 메시지 핸들러 필요
        point_info = PointReasonMap.공지사항_확인_이모지

        self._repo.add_point(
            user_id=user_id,
            reason=point_info.reason(),
            point=point_info.point(),
            category=PointCategory.OTHER,
        )

    def grant_if_curation_requested(self, user_id: str):
        """큐레이션을 요청한 경우 포인트를 지급합니다."""
        point_info = PointReasonMap.큐레이션_요청

        self._repo.add_point(
            user_id=user_id,
            reason=point_info.reason(),
            point=point_info.point(),
            category=PointCategory.WRITING,
        )

    def grant_if_curation_selected(self, user_id: str, client: AsyncWebClient):
        """
        수동: 큐레이션이 선정된 경우 포인트를 지급합니다.
        DM으로 알림을 줍니다.
        """
        point_info = PointReasonMap.큐레이션_선정

        self._repo.add_point(
            user_id=user_id,
            reason=point_info.reason(),
            point=point_info.point(),
            category=PointCategory.WRITING,
        )

        # TODO: 추가 예정
        # client.chat_postMessage()

    def grant_if_village_conference_participated(
        self, user_id: str, client: AsyncWebClient
    ):
        """
        수동: 빌리지 반상회에 참여한 경우 포인트를 지급합니다.
        DM으로 알림을 줍니다.
        """
        point_info = PointReasonMap.빌리지_반상회_참여

        self._repo.add_point(
            user_id=user_id,
            reason=point_info.reason(),
            point=point_info.point(),
            category=PointCategory.NETWORKING,
        )

        # TODO: 추가 예정
        # client.chat_postMessage()

    def grant_if_introduction_written(self, user_id: str, client: AsyncWebClient):
        """
        수동: 자기소개를 작성한 경우 포인트를 지급합니다.
        DM으로 알림을 줍니다.
        """
        point_info = PointReasonMap.자기소개_작성

        self._repo.add_point(
            user_id=user_id,
            reason=point_info.reason(),
            point=point_info.point(),
            category=PointCategory.OTHER,
        )

        # TODO: 추가 예정
        # client.chat_postMessage()

    # TODO: 추가 예정
    # def grant_user_to_user_points(self, user_id: str, target_user_id: str, point: int, reason: str, client: AsyncWebClient):
    #     """유저가 다른 유저에게 포인트를 지급합니다."""
    #     self._repo.add_point(
    #         user_id=target_user_id,
    #         giver_user_id=user_id,
    #         reason=reason,
    #         point=point,
    #         category=PointCategory.USER_TO_USER,
    #     )

    #     client.chat_postMessage()
