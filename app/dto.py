from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Submission:
    dt: str
    user_id: str
    username: str
    content_url: str
    category: str
    description: str
    tag: str
    type: Literal["submission"] = "submission"


@dataclass(frozen=True)
class Pass:
    dt: str
    user_id: str
    username: str
    description: str
    type: Literal["pass"] = "pass"
