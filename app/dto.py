from typing import Any, TypedDict

from app.models import ArchiveMessage, TriggerMessage

from pydantic import BaseModel, Field


class Content(TypedDict):
    user_id: str
    name: str
    title: str
    content_url: str
    dt: str
    category: str
    tags: str


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
                    "relevance": 1,
                    "name": "김현준",
                }
            ]
        ],
    )


class TriggerMessageResponse(BaseModel):
    count: int = Field(..., description="조건에 맞는 트리거 메시지의 총 개수", examples=[1])
    data: list[TriggerMessage] = Field(..., description="조회된 트리거 메시지의 배열")


class ArchiveMessageResponse(BaseModel):
    count: int = Field(..., description="조건에 맞는 아카이브 메시지의 총 개수", examples=[1])
    data: list[ArchiveMessage] = Field(..., description="조회된 아카이브 메시지의 배열")
