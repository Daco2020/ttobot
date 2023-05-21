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

    def to_list_for_sheet(self) -> str:
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


class User(BaseModel):
    user_id: str
    name: str
    channel_name: str
    channel_id: str
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
        prev_due_date = DUE_DATES[-2]
        for i, due_date in enumerate(DUE_DATES):
            if now_date <= due_date:
                prev_due_date = DUE_DATES[i - 2]
                break
        return prev_due_date < recent_content.date <= now_date

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
