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
        return 1

    @property
    def before_type(self) -> str:
        return "submit"
