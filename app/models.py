from __future__ import annotations

from abc import abstractmethod

from enum import Enum
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field, field_validator
import datetime
from app.constants import DUE_DATES, MAX_PASS_COUNT
from app.exception import BotException

from app.utils import generate_unique_id, tz_now, tz_now_to_str


class User(BaseModel):
    user_id: str  # 슬랙 아이디
    name: str  # 이름
    channel_name: str  # 코어채널 이름
    channel_id: str  # 코어채널 아이디
    intro: str  # 자기소개
    deposit: str = ""  # 예치금
    cohort: str = ""  # 기수
    contents: list[Content] = []  # 제출한 콘텐츠

    @field_validator("contents", mode="before")
    def get_contents(cls, v: list[Content]) -> list[Content]:
        """콘텐츠를 생성일시 오름차순으로 정렬하여 반환합니다."""
        return sorted(v, key=lambda content: content.dt_)

    @property
    def pass_count(self) -> int:
        """pass 횟수를 반환합니다."""
        return len([content for content in self.contents if content.type == "pass"])

    @property
    def is_prev_pass(self) -> bool:
        """직전에 pass 했는지 여부를 반환합니다."""
        try:
            recent_content = self.recent_content
        except Exception:
            return False

        if recent_content.type != "pass":
            return False

        return self._is_prev_pass(recent_content)

    def _is_prev_pass(self, recent_content: Content) -> bool:
        """전전회차 마감일 초과, 현재 날짜 이하 사이에 pass 했는지 여부를 반환합니다."""
        now_date = tz_now().date()
        second_latest_due_date = DUE_DATES[-2]
        for i, due_date in enumerate(DUE_DATES):
            if now_date <= due_date:
                second_latest_due_date = DUE_DATES[i - 2]
                break
        return second_latest_due_date < recent_content.date <= now_date

    @property
    def recent_content(self) -> Content:
        """최근 콘텐츠를 반환합니다."""
        return self.contents[-1]

    @property
    def content_urls(self) -> list[str]:
        """유저의 모든 콘텐츠 url 을 반환합니다."""
        return [content.content_url for content in self.contents]

    def fetch_contents(self, descending: bool = False) -> list[Content]:
        """콘텐츠를 생성일시 내림차순으로 정렬하여 반환합니다."""
        if descending:
            return sorted(self.contents, key=lambda content: content.dt_, reverse=True)
        return self.contents

    def get_due_date(self) -> tuple[int, datetime.date]:
        """현재 회차와 마감일을 반환합니다."""
        now_date = tz_now().date()
        for i, due_date in enumerate(DUE_DATES):
            if now_date <= due_date:
                round = i
                return round, due_date
        raise BotException("지금은 글또 글 제출 기간이 아니에요.")

    @property
    def is_submit(self) -> bool:
        """현재 회차의 제출여부를 반환합니다."""
        try:
            recent_content = self.recent_content
        except Exception:
            return False

        if recent_content.type != "submit":
            return False

        now_date = tz_now().date()
        for i, due_date in enumerate(DUE_DATES):
            if now_date <= due_date:  # 현재 날짜가 보다 같거나 크면 현재 마감일이다.
                # 현재 마감일의 직전 마감일을 구한다.
                latest_due_date = DUE_DATES[i - 1]
                break

        # 최근 제출한 콘텐츠의 날짜가 직전 마감일 초과, 현재 날짜 이하 라면 제출했다고 판단한다.
        return latest_due_date < recent_content.date <= now_date

    def get_submit_status(self) -> dict[int, str]:
        """현재 회차는 제외한 회차별 제출 여부를 반환합니다."""
        submit_status = {}
        for i, due_date in enumerate(DUE_DATES):
            # 0회차는 시작일이므로 제외한다.
            if i == 0:
                continue

            # 현재 회차는 제출 여부를 판단하지 않는다.
            if due_date >= tz_now().date():
                break

            # 기본값은 미제출
            submit_status[i] = "미제출"

            # 콘텐츠의 제출 날짜가 직전 마감일 초과, 마감일 이하 라면 제출했다고 판단한다.
            for content in self.fetch_contents():
                latest_due_date = DUE_DATES[i - 1]
                if latest_due_date < content.date <= due_date:
                    if content.type == "submit":
                        submit_status[i] = "제출"
                    elif content.type == "pass":
                        submit_status[i] = "패스"
                    else:
                        submit_status[i] = "미제출"

        return submit_status

    def get_continuous_submit_count(self) -> int:
        """내림차순으로 연속으로 제출한 횟수를 반환합니다."""
        count = 0
        submit_status = self.get_submit_status()
        for _, v in sorted(submit_status.items(), reverse=True):
            if v == "제출":
                count += 1
            elif v == "패스":  # 패스는 연속 제출 횟수에 포함하지 않는다.
                continue
            else:  # 미제출은 연속 제출 횟수를 끊는다.
                break
        print("submit_status", submit_status)
        print("count", count)
        return count

    def check_channel(self, channel_id: str) -> None:
        """코어 채널이 일치하는지 체크합니다."""
        if self.channel_id == "ALL":
            return
        if self.channel_id != channel_id:
            raise BotException(
                f"{self.name} 님의 코어 채널 <#{self.channel_id}> 에서 다시 시도해주세요."
            )

    @property
    def submission_guide_message(self) -> str:
        """제출 모달 가이드 메시지를 반환합니다."""
        round, due_date = self.get_due_date()
        guide_message = f"현재 회차는 {round}회차, 마감일은 {due_date} 이에요."
        if self.is_submit:
            guide_message += f"\n({self.name} 님은 이미 {round}회차 글을 제출했어요)"
        else:
            guide_message += (
                f"\n({self.name} 님은 아직 {round}회차 글을 제출하지 않았어요)"
            )
        guide_message += (
            f"\n제출 메시지는 코어 채널인 <#{self.channel_id}> 에 표시됩니다."
        )
        return guide_message

    def check_pass(self) -> None:
        """pass 사용 가능 여부를 체크합니다."""
        if self.pass_count >= MAX_PASS_COUNT:
            message = "사용할 수 있는 pass 가 없어요."
            raise BotException(message)
        if self.is_prev_pass:
            message = (
                "직전 회차에 pass 를 사용했기 때문에 연속으로 pass 를 사용할 수 없어요."
            )
            raise BotException(message)

    def to_list_for_sheet(self) -> list[str]:
        return [
            self.user_id,
            self.channel_name,
            self.name,
            self.channel_id,
            self.intro,
            self.cohort,
        ]


class SimpleUser(BaseModel):
    user_id: str
    name: str
    channel_name: str
    channel_id: str
    intro: str
    cohort: str


class StoreModel(BaseModel):
    ...

    @abstractmethod
    def to_list_for_csv(self) -> list[str]:
        """csv 파일에 쓰기 위한 리스트를 반환합니다."""
        ...

    @abstractmethod
    def to_list_for_sheet(self) -> list[str]:
        """구글 시트에 쓰기 위한 리스트를 반환합니다."""
        ...


class Content(StoreModel):
    dt: str = Field(default_factory=tz_now_to_str)
    user_id: str
    username: str
    description: str = ""
    type: str
    content_url: str = ""
    title: str = ""
    category: str = ""
    tags: str = ""
    curation_flag: str = "N"  # "Y", "N"
    ts: str = ""

    def __hash__(self) -> int:
        return hash(self.ts)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Content):
            return NotImplemented
        return self.ts == other.ts

    @property
    def dt_(self) -> datetime.datetime:
        """생성일시를 datetime 객체로 반환합니다."""
        return datetime.datetime.strptime(self.dt, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=ZoneInfo("Asia/Seoul")
        )

    @property
    def date(self) -> datetime.date:
        """생성일시를 date 객체로 반환합니다."""
        return self.dt_.date()

    def to_list_for_csv(self) -> list[str]:
        return [
            self.user_id,
            self.username,
            self.title,
            self.content_url,
            self.dt,
            self.category,
            self.description,
            self.type,
            self.tags,
            self.curation_flag,
            self.ts,
        ]

    def to_list_for_sheet(self) -> list[str]:
        return [
            self.user_id,
            self.username,
            self.title,
            self.content_url,
            self.dt,
            self.category,
            self.description,
            self.type,
            self.tags,
            self.curation_flag,
            self.ts,
        ]

    def get_round(self) -> int:
        """컨텐츠의 회차를 반환합니다."""
        for i, due_date in enumerate(DUE_DATES):
            if self.date <= due_date:
                return i
        raise BotException("글또 활동 기간이 아니에요.")

    @classmethod
    def fieldnames(self) -> list[str]:
        return [
            "user_id",
            "username",
            "title",
            "content_url",
            "dt",
            "category",
            "description",
            "type",
            "tags",
            "curation_flag",
            "ts",
        ]


class BookmarkStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"


class Bookmark(StoreModel):
    user_id: str
    content_user_id: str
    content_ts: str  # content fk 역할을 한다.
    note: str = ""
    status: BookmarkStatusEnum = BookmarkStatusEnum.ACTIVE
    created_at: str = Field(default_factory=tz_now_to_str)
    updated_at: str = Field(default_factory=tz_now_to_str)

    def to_list_for_csv(self) -> list[str]:
        return [
            self.user_id,
            self.content_user_id,
            self.content_ts,
            self.note,
            self.status,
            self.created_at,
            self.updated_at,
        ]

    def to_list_for_sheet(self) -> list[str]:
        return [
            self.user_id,
            self.content_user_id,
            self.content_ts,
            self.note,
            self.status,
            self.created_at,
            self.updated_at,
        ]


class CoffeeChatProof(StoreModel):
    ts: str  # id
    thread_ts: str = ""  # 스레드로 인증한 경우 상위 id 추가
    user_id: str
    text: str
    image_urls: str = ""  # url1,url2,url3 형태
    selected_user_ids: str = ""  # id1,id2,id3 형태
    participant_call_thread_ts: str = ""  # 커피챗 참여자 호출 스레드 id
    created_at: str = Field(default_factory=tz_now_to_str)

    def to_list_for_csv(self) -> list[str]:
        return [
            self.ts,
            self.thread_ts,
            self.user_id,
            self.text,
            self.image_urls,
            self.selected_user_ids,
            self.participant_call_thread_ts,
            self.created_at,
        ]

    def to_list_for_sheet(self) -> list[str]:
        return [
            self.ts,
            self.thread_ts,
            self.user_id,
            self.text,
            self.image_urls,
            self.selected_user_ids,
            self.participant_call_thread_ts,
            self.created_at,
        ]

    @classmethod
    def fieldnames(self) -> list[str]:
        return [
            "ts",
            "thread_ts",
            "user_id",
            "text",
            "image_urls",
            "selected_user_ids",
            "participant_call_thread_ts",
            "created_at",
        ]


class PointCategory(str, Enum):
    WRITING = "글쓰기"
    NETWORKING = "네트워크"
    USER_TO_USER = "유저 간"
    OTHER = "기타"


class PointHistory(BaseModel):
    id: str = Field(default_factory=generate_unique_id)
    user_id: str
    reason: str
    point: int
    category: PointCategory | str
    created_at: str = Field(default_factory=tz_now_to_str)

    def to_list_for_csv(self) -> list[str]:
        return [
            self.id,
            self.user_id,
            self.reason,
            str(self.point),
            self.category,
            self.created_at,
        ]

    def to_list_for_sheet(self) -> list[str]:
        return [
            self.id,
            self.user_id,
            self.reason,
            str(self.point),
            self.category,
            self.created_at,
        ]

    @classmethod
    def fieldnames(self) -> list[str]:
        return [
            "id",
            "user_id",
            "reason",
            "point",
            "category",
            "created_at",
        ]


class PaperPlane(StoreModel):
    id: str = Field(default_factory=generate_unique_id)
    sender_id: str
    sender_name: str
    receiver_id: str
    receiver_name: str
    text: str
    text_color: str
    bg_color: str
    color_label: str
    created_at: str = Field(default_factory=tz_now_to_str)

    def to_list_for_csv(self) -> list[str]:
        return [
            self.id,
            self.sender_id,
            self.sender_name,
            self.receiver_id,
            self.receiver_name,
            self.text,
            self.text_color,
            self.bg_color,
            self.color_label,
            self.created_at,
        ]

    def to_list_for_sheet(self) -> list[str]:
        return [
            self.id,
            self.sender_id,
            self.sender_name,
            self.receiver_id,
            self.receiver_name,
            self.text,
            self.text_color,
            self.bg_color,
            self.color_label,
            self.created_at,
        ]


class SubscriptionStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"


class Subscription(StoreModel):
    id: str = Field(default_factory=generate_unique_id)
    user_id: str
    target_user_id: str
    status: SubscriptionStatusEnum = SubscriptionStatusEnum.ACTIVE
    created_at: str = Field(default_factory=tz_now_to_str)
    updated_at: str = ""

    def to_list_for_sheet(self) -> list[str]:
        return [
            self.id,
            self.user_id,
            self.target_user_id,
            self.status,
            self.created_at,
            self.updated_at,
        ]

    def to_list_for_csv(self) -> list[str]:
        return [
            self.id,
            self.user_id,
            self.target_user_id,
            self.status,
            self.created_at,
            self.updated_at,
        ]
