from zoneinfo import ZoneInfo
from pydantic import BaseModel
import datetime
from app.config import DUE_DATE

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
        return len([content for content in self.contents if content.type == "pass"])

    @property
    def is_prev_pass(self) -> bool:
        try:
            recent_content = self.recent_content
        except Exception:
            return False

        if recent_content.type != "pass":
            return False

        prev_start_date, end_date = self._get_prev_dates()
        return prev_start_date < recent_content.date <= end_date

    def _get_prev_dates(self):
        prev_start_date = DUE_DATE[-2]
        end_date = now_dt().date()
        for i, date in enumerate(DUE_DATE):
            if date >= end_date:
                prev_start_date = DUE_DATE[i - 2]
                break
        return prev_start_date, end_date

    @property
    def recent_content(self) -> Content:
        return self.contents[-1]

    @property
    def content_urls(self) -> list[str]:
        return [content.content_url for content in self.contents]

    def fetch_contents(self) -> list[Content]:
        return self.contents
