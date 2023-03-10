from zoneinfo import ZoneInfo
from pydantic import BaseModel
import datetime


class Content(BaseModel):
    dt: str
    user_id: str
    username: str
    description: str
    type: str
    content_url: str = ""
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

    def to_line(self) -> str:
        return ",".join(
            [
                self.user_id,
                self.username,
                self.content_url,
                self.dt,
                self.category,
                self.description.replace(",", "").replace("\n", " "),
                self.type,
                self.tags.replace(",", "#"),
            ]
        )


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
    def before_type(self) -> str:
        # TODO: 추후 날짜기반 으로 변경
        if not self.contents:
            return ""
        return self.recent_content.type

    @property
    def recent_content(self) -> Content:
        return self.contents[-1]

    @property
    def content_urls(self) -> list[str]:
        return [content.content_url for content in self.contents]

    def fetch_contents(self) -> list[Content]:
        return self.contents
