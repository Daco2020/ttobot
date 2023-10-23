from enum import Enum
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field
import datetime
from app.config import DUE_DATES

from app.utils import now_dt, now_dt_to_str


class Content(BaseModel):
    dt: str = Field(default_factory=now_dt_to_str)
    user_id: str
    username: str
    description: str = ""
    type: str
    content_url: str = ""
    title: str = ""
    category: str = ""
    tags: str = ""

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

    def to_list_for_csv(self) -> list[str]:
        """csv 파일에 쓰기 위한 한 줄을 반환합니다."""
        return [
            self.user_id,
            self.username,
            self.title,
            self.content_url,
            self.dt,
            self.category,
            self.description,
            self.type,
            self.tags.replace(",", "#"),
        ]

    def to_list_for_sheet(self) -> list[str]:
        """구글 시트에 쓰기 위한 리스트를 반환합니다."""
        return [
            self.user_id,
            self.username,
            self.title,
            self.content_url,
            self.dt,
            self.category,
            self.description,
            self.type,
            self.tags.replace(",", "#"),
        ]

    def get_round(self) -> int:
        """컨텐츠의 회차를 반환합니다."""
        for i, due_date in enumerate(DUE_DATES):
            if self.date <= due_date:
                return i + 1
        raise ValueError("글또 활동 기간이 아닙니다.")


class User(BaseModel):
    user_id: str
    name: str
    channel_name: str
    channel_id: str
    intro: str
    deposit: int
    animal_type: str = ""
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
        now_date = now_dt().date()
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
        now_date = now_dt().date()
        for i, due_date in enumerate(DUE_DATES):
            if now_date <= due_date:
                round = i + 1
                return round, due_date
        raise ValueError("글또 활동 기간이 아닙니다.")

    @property
    def is_submit(self) -> bool:
        """현재 회차의 제출여부를 반환합니다."""
        try:
            recent_content = self.recent_content
        except Exception:
            return False

        if recent_content.type != "submit":
            return False

        now_date = now_dt().date()
        latest_due_date = DUE_DATES[-2]
        for i, due_date in enumerate(DUE_DATES):
            if now_date <= due_date:
                latest_due_date = DUE_DATES[i - 1]
                break
        return latest_due_date < recent_content.date <= now_date


class BookmarkStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"


class Bookmark(BaseModel):
    user_id: str
    content_id: str  # user_id:dt 형식의 유니크 키
    note: str = ""
    status: BookmarkStatusEnum = BookmarkStatusEnum.ACTIVE
    created_at: str = Field(default_factory=now_dt_to_str)
    updated_at: str = Field(default_factory=now_dt_to_str)

    def to_list_for_csv(self) -> list[str]:
        """csv 파일에 쓰기 위한 리스트를 반환합니다."""
        return [
            self.user_id,
            self.content_id,
            self.note,
            self.status,
            self.created_at,
            self.updated_at,
        ]

    def to_list_for_sheet(self) -> list[str]:
        """구글 시트에 쓰기 위한 리스트를 반환합니다."""
        return [
            self.user_id,
            self.content_id,
            self.note,
            self.status,
            self.created_at,
            self.updated_at,
        ]
