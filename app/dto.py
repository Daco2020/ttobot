from dataclasses import dataclass


@dataclass(frozen=True)
class Submission:
    dt: str
    user_id: str
    username: str
    content_url: str
    category: str
    description: str
    tag: str
