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
                    "cohort": "9기",
                    "relevance": 1,
                }
            ]
        ],
    )
