from pydantic import BaseModel
from app.exception import BotException
from app.models import PointHistory, User
from app.slack.repositories import SlackRepository
from app.config import settings
from app import store
from enum import Enum

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

    def set_point(self, point: int) -> None:
        self.value["point"] = point

    @property
    def point(self) -> int:
        return self.value["point"]

    @property
    def reason(self) -> str:
        return self.value["reason"]

    @property
    def category(self) -> str:
        return self.value["category"]


class UserPoint(BaseModel):
    user: User
    point_histories: list[PointHistory]
    
    @property
    def total_point(self) -> int:
        return sum([point_history.point for point_history in self.point_histories])


    @property
    def point_history_text(self) -> str:
        text = ""
        for point_history in self.point_histories[:20]:
            text += f"[{point_history.created_at}] - *{point_history.point}점* :: {point_history.reason}\n"

        if not text:
            text = "아직 포인트 획득 내역이 없어요. 😅\n또봇 [홈] 탭 -> [포인트 획득 방법 알아보기] 에서 방법을 확인해보세요."

        return text



class PointService:
    def __init__(self, repo: SlackRepository) -> None:
        self._repo = repo

    def get_user_point(self, user_id: str) -> UserPoint:
        """포인트 히스토리를 포함한 유저를 가져옵니다."""
        user = self._repo.get_user(user_id)
        if not user:
            raise BotException("존재하지 않는 유저입니다.")
        point_histories = self._repo.fetch_point_histories(user_id)
        return UserPoint(user=user, point_histories=point_histories)

    def add_point_history(self, user_id: str, point_info: PointMap) -> str:
        """포인트 히스토리를 추가하고 알림 메시지를 반환합니다."""
        point_history=PointHistory(
            user_id=user_id,
            reason=point_info.reason,
            point=point_info.point,
            category=point_info.category,
        )
        self._repo.add_point(point_history=point_history)
        store.point_history_upload_queue.append(point_history.to_list_for_sheet())
        return f"<@{user_id}>님 `{point_info.reason}`(으)로 `{point_info.point}`포인트를 획득했어요! 🎉\n획득한 총 포인트는 또봇 [홈] 탭에서 확인할 수 있어요."

    def grant_if_post_submitted(self, user_id: str) -> tuple[str, bool]:
        """글쓰기 포인트 지급 1. 글을 제출하면 기본 포인트를 지급합니다. 글을 이미 제출했다면 추가 포인트를 지급합니다."""
        user = self._repo.get_user(user_id)

        if not user:
            raise BotException("유저 정보가 없어 글 제출 포인트를 지급할 수 없습니다.")

        if user.is_submit:
            is_additional = True
            point_info = PointMap.글_제출_추가
            return self.add_point_history(user_id, point_info), is_additional
        else: 
            is_additional = False
            point_info = PointMap.글_제출_기본
            return self.add_point_history(user_id, point_info), is_additional
        
    def grant_if_post_submitted_continuously(self, user_id: str) -> str | None:
        """글쓰기 포인트 지급 2. 글을 연속으로 제출한다면 추가 포인트를 지급합니다."""
        user = self._repo.get_user(user_id)

        if not user:
            raise BotException("유저 정보가 없어 글 제출 포인트를 지급할 수 없습니다.")
        
        continuous_submit_count = user.get_continuous_submit_count()
        if continuous_submit_count > 1: # 1보다 크면 연속 제출이므로 추가 포인트 지급
            if continuous_submit_count == 9:
                point_info = PointMap.글_제출_9콤보_보너스
            elif continuous_submit_count == 6:
                point_info = PointMap.글_제출_6콤보_보너스
            elif continuous_submit_count == 3:
                point_info = PointMap.글_제출_3콤보_보너스
            else:
                # 3,6,9 외에는 연속 제출 횟수에 따라 연속 포인트를 지급합니다.
                point_info = PointMap.글_제출_콤보
                combo_point = point_info.point * (continuous_submit_count - 1) # 2부터 연속 제출이므로 -1
                point_info.set_point(combo_point)
                
            return self.add_point_history(user_id, point_info)
        
        return None

    def grant_if_post_submitted_to_core_channel_ranking(self, user_id: str) -> str | None:
        """글 제출 포인트 지급 3. 코어채널 제출 순위에 따라 추가 포인트를 지급합니다."""
        user = self._repo.get_user(user_id)

        if not user:
            raise BotException("유저 정보가 없어 글 제출 포인트를 지급할 수 없습니다.")
        
        rank_map = {}
        channel_users = self._repo.fetch_channel_users(user.channel_id)
        for channel_user in channel_users:
            if channel_user.is_submit is True:
                content = channel_user.recent_content
                rank_map[channel_user.user_id] = content.ts
        
        rank_user_ids = sorted(rank_map, key=lambda x: rank_map[x], reverse=True)[:3]
        if user.user_id in rank_user_ids:
            rank = rank_user_ids.index(user.user_id) + 1
            if rank == 1:
                point_info = PointMap.글_제출_코어채널_1등
            elif rank == 2:
                point_info = PointMap.글_제출_코어채널_2등
            else:
                point_info = PointMap.글_제출_코어채널_3등

            return self.add_point_history(user_id, point_info)
        
        return None

    def grant_if_coffee_chat_verified(self, user_id: str) -> str:
        """
        공개: 커피챗 인증을 한 경우 포인트를 지급합니다.
        공개채널에 알림을 줍니다.
        """
        point_info = PointMap.커피챗_인증
        return self.add_point_history(user_id, point_info)

    def grant_if_notice_emoji_checked(self, user_id: str) -> str:
        """공지사항을 확인한 경우 포인트를 지급합니다."""
        point_info = PointMap.공지사항_확인_이모지
        return self.add_point_history(user_id, point_info)

    def grant_if_curation_requested(self, user_id: str) -> str:
        """큐레이션을 요청한 경우 포인트를 지급합니다."""
        point_info = PointMap.큐레이션_요청
        return self.add_point_history(user_id, point_info)

    def grant_if_curation_selected(self, user_id: str) -> str:
        """
        수동: 큐레이션이 선정된 경우 포인트를 지급합니다.
        DM으로 알림을 줍니다.
        """
        point_info = PointMap.큐레이션_선정
        return self.add_point_history(user_id, point_info)


    def grant_if_village_conference_participated(
        self, user_id: str
    ):
        """
        수동: 빌리지 반상회에 참여한 경우 포인트를 지급합니다.
        DM으로 알림을 줍니다.
        """
        point_info = PointMap.빌리지_반상회_참여
        return self.add_point_history(user_id, point_info)

    def grant_if_introduction_written(self, user_id: str) -> str:
        """
        수동: 자기소개를 작성한 경우 포인트를 지급합니다.
        DM으로 알림을 줍니다.
        """
        point_info = PointMap.자기소개_작성
        return self.add_point_history(user_id, point_info)
