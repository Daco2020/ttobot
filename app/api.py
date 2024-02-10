import polars as pl

from typing import Any

from starlette import status
from fastapi import APIRouter, Depends
from app.constants import ArchiveMessageSortEnum, ContentCategoryEnum, ContentSortEnum
from app.deps import get_app_service
from app.services import AppService

from app.utils import translate_keywords


router = APIRouter()


@router.get(
    "/contents",
    status_code=status.HTTP_200_OK,
)
async def fetch_contents(
    keyword: str,
    offset: int = 0,
    limit: int = 10,
    category: ContentCategoryEnum | None = None,
    order_by: ContentSortEnum = ContentSortEnum.DT,
    descending: bool = True,
) -> list[Any]:
    """조건에 맞는 콘텐츠를 가져옵니다."""
    # TODO: 기수(period) 정보를 유저정보에 추가하기
    # TODO: LIKE 컬럼 추가하기
    # TODO: 결과가 없을 경우, 글감 추천하기 <- 클라이언트가 처리

    # 원본 데이터 불러오기
    users_df = pl.read_csv(
        "store/users.csv",
        columns=[
            "user_id",
            "name",
        ],
    )
    contents_df = pl.read_csv(
        "store/contents.csv",
        columns=[
            "user_id",
            "title",
            "content_url",
            "dt",
            "category",
            "tags",
        ],
    )
    if category:
        contents_df = contents_df.filter(contents_df["category"] == category)

    # 키워드 추출, TODO: 명사 단위로 쪼개서 검색하기
    keywords = [
        keyword
        for keyword in keyword.replace(",", " ").replace("/", " ").split(" ")
        if keyword
    ]
    keywords.extend(translate_keywords(keywords))

    # 키워드 매칭
    matched_dfs = [
        contents_df.filter(
            contents_df.apply(lambda row: match_keyword(keyword, row)).to_series()
        )
        for keyword in set(keywords)
    ]
    if not matched_dfs:
        return []

    # 관련도 추가
    combined_df: pl.DataFrame = pl.concat(matched_dfs)
    grouped_df = combined_df.groupby("content_url").agg(pl.count().alias("relevance"))

    contents = (
        combined_df.unique(subset=["content_url"])
        .join(grouped_df, on="content_url", how="inner")
        .join(users_df, on="user_id", how="inner")
        .sort([order_by, "dt"], descending=[True, descending])
        .slice(offset, limit)
        .to_dicts()
    )
    return contents


def match_keyword(keyword: str, row: tuple) -> bool:
    return keyword in f"{row[1]},{row[5]}".lower()  # title, tags


@router.get(
    "/archive_messages",
    status_code=status.HTTP_200_OK,
)
async def fetch_archive_messages(
    offset: int = 0,
    limit: int = 10,
    user_id: str | None = None,
    search_word: str | None = None,
    trigger_word: str | None = None,
    order_by: ArchiveMessageSortEnum = ArchiveMessageSortEnum.DT,
    descending: bool = True,
    service: AppService = Depends(get_app_service),
) -> None:
    """조건에 맞는 아카이브 메시지를 가져옵니다."""
