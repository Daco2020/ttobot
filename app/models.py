from __future__ import annotations

from abc import abstractmethod
from enum import Enum
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field, field_validator
import datetime
from app.constants import DUE_DATES
from app.slack.exception import BotException

from app.utils import slack_link_to_markdown, tz_now, tz_now_to_str


class User(BaseModel):
    user_id: str
    name: str
    channel_name: str
    channel_id: str
    intro: str
    deposit: str = ""
    contents: list[Content] = []

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

    def fetch_contents(self) -> list[Content]:
        """유저의 모든 콘텐츠를 반환합니다."""
        return self.contents

    def get_due_date(self) -> tuple[int, datetime.date]:
        """현재 회차와 마감일을 반환합니다."""
        now_date = tz_now().date()
        for i, due_date in enumerate(DUE_DATES):
            if now_date <= due_date:
                round = i
                return round, due_date
        raise BotException("글또 활동 기간이 아니에요.")

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

    def to_list_for_sheet(self) -> list[str]:
        return [
            self.user_id,
            self.channel_name,
            self.name,
            self.channel_id,
            self.intro,
        ]


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

    def __hash__(self) -> int:
        return hash(self.content_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Content):
            return NotImplemented
        return self.content_id == other.content_id

    @property
    def content_id(self) -> str:
        """컨텐츠 아이디를 반환합니다."""
        return f"{self.user_id}:{self.dt}"

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

    @field_validator("title", mode="before")
    def get_title(cls, v: str) -> str:
        """간혹 글 제목에 개행문자가 들어가는 경우가 있어서 개행문자를 공백으로 치환합니다."""
        return v.replace("\n", " ")

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
        ]

    def get_round(self) -> int:
        """컨텐츠의 회차를 반환합니다."""
        for i, due_date in enumerate(DUE_DATES):
            if self.date <= due_date:
                return i
        raise BotException("글또 활동 기간이 아니에요.")


class BookmarkStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"


class Bookmark(StoreModel):
    user_id: str
    content_id: str  # user_id:dt 형식의 유니크 키
    note: str = ""
    status: BookmarkStatusEnum = BookmarkStatusEnum.ACTIVE
    created_at: str = Field(default_factory=tz_now_to_str)
    updated_at: str = Field(default_factory=tz_now_to_str)

    def to_list_for_csv(self) -> list[str]:
        return [
            self.user_id,
            self.content_id,
            self.note,
            self.status,
            self.created_at,
            self.updated_at,
        ]

    def to_list_for_sheet(self) -> list[str]:
        return [
            self.user_id,
            self.content_id,
            self.note,
            self.status,
            self.created_at,
            self.updated_at,
        ]


class TriggerMessage(StoreModel):
    user_id: str = Field(
        ...,
        description="유저의 슬랙 아이디",
        examples=["U01UJ9MUADT"],
    )
    channel_id: str = Field(
        ...,
        description="채널 아이디",
        examples=["C01B4PVGLVB"],
    )
    trigger_word: str = Field(
        ...,
        description="트리거 단어",
        examples=["$인사이트"],
    )
    created_at: str = Field(
        default_factory=tz_now_to_str,
        description="생성 일시",
        examples=["2021-03-16 00:00:00"],
    )

    def to_list_for_csv(self) -> list[str]:
        return [
            self.user_id,
            self.channel_id,
            self.trigger_word,
            self.created_at,
        ]

    def to_list_for_sheet(self) -> list[str]:
        return [
            self.user_id,
            self.channel_id,
            self.trigger_word,
            self.created_at,
        ]


class ArchiveMessage(StoreModel):
    ts: str = Field(
        ...,
        description="메시지 생성 타임스탬프",
        examples=["1615844583.000100"],
    )
    channel_id: str = Field(
        ...,
        description="채널 아이디",
        examples=["C01B4PVGLVB"],
    )
    trigger_word: str = Field(
        ...,
        description="트리거 단어",
        examples=["$인사이트"],
    )
    user_id: str = Field(
        ...,
        description="유저의 슬랙 아이디",
        examples=["U01UJ9MUADT"],
    )
    message: str = Field(
        ...,
        description="슬랙 메시지",
        examples=["안녕하세요!"],
    )
    file_urls: str = Field(
        ...,
        description="첨부한 파일 url",
        examples=["https://image1.jpg,https://image2.jpg,https://image3.jpg"],
    )
    updated_at: str = Field(
        default_factory=tz_now_to_str,
        description="업데이트 일시",
        examples=["2021-03-16 00:00:00"],
    )

    @field_validator("ts", mode="before")
    def get_ts(cls, v: str | float) -> str:
        return str(v)

    @field_validator("message", mode="before")
    def get_message(cls, v: str) -> str:
        return (
            slack_link_to_markdown(v)
            .replace("\n", "<br>")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&nbsp;", " ")
            .replace("&amp;", "&")
        )

    def to_list_for_csv(self) -> list[str]:
        return [
            self.ts,
            self.channel_id,
            self.trigger_word,
            self.user_id,
            self.message,
            self.file_urls,
            self.updated_at,
        ]

    def to_list_for_sheet(self) -> list[str]:
        return [
            self.ts,
            self.channel_id,
            self.trigger_word,
            self.user_id,
            self.message,
            self.file_urls,
            self.updated_at,
        ]


class FeedbackRequest(StoreModel):
    ts: str = ""
    user_id: str
    content_url: str
    title: str
    category: str
    tags: str
    message: str

    def to_list_for_csv(self) -> list[str]:
        return [
            self.ts,
            self.user_id,
            self.content_url,
            self.title,
            self.category,
            self.tags,
            self.message,
        ]

    def to_list_for_sheet(self) -> list[str]:
        return [
            self.ts,
            self.user_id,
            self.content_url,
            self.title,
            self.category,
            self.tags,
            self.message,
        ]


class FeedbackResponse(StoreModel):
    ts: str
    request_ts: str
    user_id: str
    message: str

    def to_list_for_csv(self) -> list[str]:
        return [
            self.ts,
            self.request_ts,
            self.user_id,
            self.message,
        ]

    def to_list_for_sheet(self) -> list[str]:
        return [
            self.ts,
            self.request_ts,
            self.user_id,
            self.message,
        ]
