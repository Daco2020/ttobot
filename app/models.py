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
    def datetime(self) -> datetime.datetime:
        return datetime.datetime.strptime(self.dt, "%Y-%m-%d %H:%M:%S")

    def to_line(self) -> str:
        return ",".join(
            [
                self.user_id,
                self.username,
                self.content_url,
                self.dt,
                self.category,
                self.description,
                self.type,
                self.tags,
                "\n",
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
        if not self.contents:
            return ""
        return self.recent_content.type

    @property
    def recent_content(self) -> Content:
        return self.contents[-1]

    def fetch_contents_history(self) -> list[Content]:
        # TODO: implement
        return []
