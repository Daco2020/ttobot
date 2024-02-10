from typing import TypedDict


class Content(TypedDict):
    user_id: str
    name: str
    title: str
    content_url: str
    dt: str
    category: str
    tags: str
