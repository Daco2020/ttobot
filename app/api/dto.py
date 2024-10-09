from typing import Any
from pydantic import BaseModel, Field


class ContentResponse(BaseModel):
    count: int = Field(..., description="조건에 맞는 콘텐츠의 총 개수", examples=[1])
    data: list[dict[str, Any]] = Field(
        ...,
        description="조회된 콘텐츠의 배열",
        examples=[
            [
                {
                    "user_id": "U07NTP9MGH4",
                    "title": "Python aiocache 로 비동기 Slack API 요청 캐싱하기",
                    "content_url": "https://daco2020.tistory.com/854",
                    "dt": "2024-10-03 22:31:56",
                    "category": "기술 & 언어",
                    "tags": "Python,Slack API,Cache,캐싱,비동기 함수,비동기 캐싱",
                    "ts": "1727962316.649959",
                    "name": "김은찬",
                    "cohort": "10기",
                    "job_category": "풀스택",
                    "relevance": 0,
                }
            ]
        ],
    )


class PaperPlaneResponse(BaseModel):
    count: int = Field(
        ..., description="조건에 맞는 종이비행기의 총 개수", examples=[1]
    )
    data: list[dict[str, Any]] = Field(
        ...,
        description="조회된 종이비행기의 배열",
        examples=[
            {
                "count": 1,
                "data": [
                    {
                        "id": "BLayCX1727143294282",
                        "sender_id": "U02HPESDZT3",
                        "sender_name": "김은찬",
                        "receiver_id": "U06EV0G3QUA",
                        "receiver_name": "성연찬",
                        "text": "테스트",
                        "text_color": "#FFFFFF",
                        "bg_color": "blush_rosybrown",
                        "color_label": "#BC8F8F",
                        "created_at": "2024-09-24 11:01:34",
                    }
                ],
            }
        ],
    )
