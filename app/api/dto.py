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
                    "user_id": "U066E7U9QFM",
                    "title": "[Python] PS와 코딩테스트를 위한 소소한 팁 모음 - 인생은 B와 D사이 Code다",
                    "content_url": "https://tolerblanc.github.io/python/python-for-PS/",
                    "dt": "2024-02-04 23:31:09",
                    "category": "기술 & 언어",
                    "tags": "python,코딩테스트",
                    "name": "김현준",
                    "cohort": "10기",
                    "relevance": 1,
                }
            ]
        ],
    )


class PaperAirplaneResponse(BaseModel):
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
