from dataclasses import dataclass


@dataclass(frozen=True)
class Submit:
    dt: str
    user_id: str
    username: str
    description: str
    type: str
    content_url: str | None = None
    category: str | None = None
    tag: str | None = None
