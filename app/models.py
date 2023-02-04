from pydantic import BaseModel


class Content(BaseModel):
    dt: str
    user_id: str
    username: str
    description: str
    type: str
    content_url: str | None = None
    category: str | None = None
    tags: str | None = None


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
        return self.contents.pop().type

    def fetch_content_histories(self) -> list[Content]:
        # TODO: implement
        return []
