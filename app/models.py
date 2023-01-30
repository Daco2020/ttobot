from pydantic import BaseModel


class Submission(BaseModel):
    dt: str
    user_id: str
    username: str
    description: str
    type: str
    content_url: str | None = None
    category: str | None = None
    tag: str | None = None


class User(BaseModel):
    user_id: str
    name: str
    channel_name: str
    channel_id: str
    submission: list[Submission]
