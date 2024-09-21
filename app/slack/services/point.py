from pydantic import BaseModel
from app.exception import BotException
from app.models import PointHistory, User
from app.slack.repositories import SlackRepository
from slack_sdk.web.async_client import AsyncWebClient
from app.config import settings
from app import store
from enum import Enum

# TODO: 주고 받기, 피드백 등은 구체화 후 추가 예정
# 동기부여와 자극을 주는 포인트는 공개 채널에 알림을 준다.
# 수동으로 받는 포인트는 디엠 으로 알림을 준다.

# fmt: off
class PointMap(Enum):
    글_제출_기본 = settings.POINT_MAP["글_제출_기본"]
    글_제출_추가 = settings.POINT_MAP["글_제출_추가"]
    글_제출_콤보 = settings.POINT_MAP["글_제출_콤보"]
    글_제출_3콤보_보너스 = settings.POINT_MAP["글_제출_3콤보_보너스"]
    글_제출_6콤보_보너스 = settings.POINT_MAP["글_제출_6콤보_보너스"]
    글_제출_9콤보_보너스 = settings.POINT_MAP["글_제출_9콤보_보너스"]
    글_제출_코어채널_1등 = settings.POINT_MAP["글_제출_코어채널_1등"]
    글_제출_코어채널_2등 = settings.POINT_MAP["글_제출_코어채널_2등"]
    글_제출_코어채널_3등 = settings.POINT_MAP["글_제출_코어채널_3등"]
    커피챗_인증 = settings.POINT_MAP["커피챗_인증"]
    공지사항_확인_이모지 = settings.POINT_MAP["공지사항_확인_이모지"]
    큐레이션_요청 = settings.POINT_MAP["큐레이션_요청"]
    큐레이션_선정 = settings.POINT_MAP["큐레이션_선정"]
    빌리지_반상회_참여 = settings.POINT_MAP["빌리지_반상회_참여"]
    자기소개_작성 = settings.POINT_MAP["자기소개_작성"]

# fmt: on

    @property
    def point(self):
        return self.value["point"]

    @property
    def reason(self):
        return self.value["reason"]

    @property
    def category(self):
        return self.value["category"]


class UserPointHisrory(BaseModel):
    user: User
    point_histories: list[PointHistory]
    
    @property
    def total_point(self) -> int:
        return sum([point_history.point for point_history in self.point_histories])

class PointService:
    def __init__(self, repo: SlackRepository) -> None:
        self._repo = repo

    def get_user_point_history(self, user_id: str) -> UserPointHisrory:
        """포인트 히스토리를 포함한 유저를 가져옵니다."""
        user = self._repo.get_user(user_id)
        if not user:
            raise BotException("존재하지 않는 유저입니다.")
        point_histories = self._repo.fetch_point_histories(user_id)
        return UserPointHisrory(user=user, point_histories=point_histories)


    def grant_if_post_submitted(self, user_id: str) -> None:
        """글을 제출했다면 포인트를 지급합니다."""
        point_info = PointMap.글_제출_기본

        point_history=PointHistory(
            user_id=user_id,
            reason=point_info.reason,
            point=point_info.point,
            category=point_info.category,
        )
        self._repo.add_point(point_history=point_history)
        store.point_history_upload_queue.append(point_history.to_list_for_sheet())

        # user = self._repo.get_user(user_id)

        # TODO: 추가 예정
        # if 글을 추가로 제출한다면:
        # if 글을 콤보로 제출한다면: 공개 알림
        # if 글을 3,6,9콤보로 제출한다면: 공개 알림
        # if 코어채널 제출 순위: 공개 알림

    def grant_if_coffee_chat_verified(self, user_id: str, client: AsyncWebClient) -> None:
        """
        공개: 커피챗 인증을 한 경우 포인트를 지급합니다.
        공개채널에 알림을 줍니다.
        """
        point_info = PointMap.커피챗_인증

        point_history=PointHistory(
            user_id=user_id,
            reason=point_info.reason,
            point=point_info.point,
            category=point_info.category,
        )
        self._repo.add_point(point_history=point_history)
        store.point_history_upload_queue.append(point_history.to_list_for_sheet())

        # TODO: 추가 예정
        # client.chat_postMessage()

    def grant_if_notice_emoji_checked(self, user_id: str) -> None:
        """공지사항을 확인한 경우 포인트를 지급합니다."""
        point_info = PointMap.공지사항_확인_이모지

        point_history=PointHistory(
            user_id=user_id,
            reason=point_info.reason,
            point=point_info.point,
            category=point_info.category,
        )
        self._repo.add_point(point_history=point_history)
        store.point_history_upload_queue.append(point_history.to_list_for_sheet())


    def grant_if_curation_requested(self, user_id: str) -> None:
        """큐레이션을 요청한 경우 포인트를 지급합니다."""
        point_info = PointMap.큐레이션_요청

        point_history=PointHistory(
            user_id=user_id,
            reason=point_info.reason,
            point=point_info.point,
            category=point_info.category,
        )
        self._repo.add_point(point_history=point_history)
        store.point_history_upload_queue.append(point_history.to_list_for_sheet())

    def grant_if_curation_selected(self, user_id: str, client: AsyncWebClient) -> None:
        """
        수동: 큐레이션이 선정된 경우 포인트를 지급합니다.
        DM으로 알림을 줍니다.
        """
        point_info = PointMap.큐레이션_선정

        point_history=PointHistory(
            user_id=user_id,
            reason=point_info.reason,
            point=point_info.point,
            category=point_info.category,
        )
        self._repo.add_point(point_history=point_history)
        store.point_history_upload_queue.append(point_history.to_list_for_sheet())

        # TODO: 추가 예정
        # client.chat_postMessage()

    def grant_if_village_conference_participated(
        self, user_id: str, client: AsyncWebClient
    ):
        """
        수동: 빌리지 반상회에 참여한 경우 포인트를 지급합니다.
        DM으로 알림을 줍니다.
        """
        point_info = PointMap.빌리지_반상회_참여

        point_history=PointHistory(
            user_id=user_id,
            reason=point_info.reason,
            point=point_info.point,
            category=point_info.category,
        )
        self._repo.add_point(point_history=point_history)
        store.point_history_upload_queue.append(point_history.to_list_for_sheet())

        # TODO: 추가 예정
        # client.chat_postMessage()

    def grant_if_introduction_written(self, user_id: str, client: AsyncWebClient) -> None:
        """
        수동: 자기소개를 작성한 경우 포인트를 지급합니다.
        DM으로 알림을 줍니다.
        """
        point_info = PointMap.자기소개_작성

        point_history=PointHistory(
            user_id=user_id,
            reason=point_info.reason,
            point=point_info.point,
            category=point_info.category,
        )
        self._repo.add_point(point_history=point_history)
        store.point_history_upload_queue.append(point_history.to_list_for_sheet())

        # TODO: 추가 예정
        # client.chat_postMessage()

    # TODO: 추가 예정
    # def grant_user_to_user_points(self, user_id: str, target_user_id: str, point: int, reason: str, client: AsyncWebClient) -> None:
    #     """유저가 다른 유저에게 포인트를 지급합니다."""
        # point_history=PointHistory(
        #     user_id=user_id,
        #     reason=point_info.reason,
        #     point=point_info.point,
        #     category=point_info.category,
        # )
        # self._repo.add_point(point_history=point_history)
        # store.point_history_upload_queue.append(point_history.to_list_for_sheet())

    #     client.chat_postMessage()
