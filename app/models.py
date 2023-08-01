from zoneinfo import ZoneInfo
from pydantic import BaseModel
import datetime
from app.config import DUE_DATES

from app.utils import now_dt


class Content(BaseModel):
    dt: str
    user_id: str
    username: str
    description: str = ""
    type: str
    content_url: str = ""
    title: str = ""
    category: str = ""
    tags: str = ""

    @property
    def dt_(self) -> datetime.datetime:
        return datetime.datetime.strptime(self.dt, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=ZoneInfo("Asia/Seoul")
        )

    @property
    def date(self) -> datetime.date:
        return self.dt_.date()

    def to_line_for_csv(self) -> str:
        return ",".join(
            [
                self.user_id,
                self.username,
                f'"{self.title}"',
                f'"{self.content_url}"',
                self.dt,
                self.category,
                self.description.replace(",", " ").replace("\n", " "),
                self.type,
                self.tags.replace(",", "#"),
            ]
        )

    def to_list_for_sheet(self) -> list[str]:
        return [
            self.user_id,
            self.username,
            self.title,
            self.content_url,
            self.dt,
            self.category,
            self.description.replace(",", " ").replace("\n", " "),
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
