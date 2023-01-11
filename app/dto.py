from dataclasses import dataclass
import datetime


@dataclass(frozen=True)
class Submission:
    dt: datetime.datetime
    user_id: str
    username: str
    content_url: str
    category: str
    description: str
    tag: str
