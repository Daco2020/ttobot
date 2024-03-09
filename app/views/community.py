import polars as pl

from starlette import status
from fastapi import APIRouter, Depends, Query
from app.constants import ArchiveMessageSortEnum, ContentCategoryEnum, ContentSortEnum
from app.deps import app_service
from app import dto
from app.services import AppService
from app.utils import translate_keywords


router = APIRouter()


@router.get(
    "/contents",
    status_code=status.HTTP_200_OK,
    response_model=dto.ContentResponse,
)
async def fetch_contents(
    keyword: str,
    offset: int = 0,
    limit: int = Query(default=50, le=50),
    category: ContentCategoryEnum | None = None,
    order_by: ContentSortEnum = ContentSortEnum.DT,
    descending: bool = True,
) -> dto.ContentResponse:
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
            "ts",
        ],
    )
    if category:
        contents_df = contents_df.filter(contents_df["category"] == category)

    # 키워드 추출, TODO: 명사 단위로 쪼개서 검색하기
    keywords = [
        keyword for keyword in keyword.replace(",", " ").replace("/", " ").split(" ") if keyword
    ]
    keywords.extend(translate_keywords(keywords))

    # 키워드 매칭
    matched_dfs = [
        contents_df.filter(contents_df.apply(lambda row: match_keyword(keyword, row)).to_series())
        for keyword in set(keywords)
    ]
    if not matched_dfs:
        return dto.ContentResponse(count=0, data=[])

    # 관련도 추가
    combined_df: pl.DataFrame = pl.concat(matched_dfs)
    grouped_df = combined_df.groupby("content_url").agg(pl.count().alias("relevance"))

    contents = (
        combined_df.unique(subset=["content_url"])
        .join(grouped_df, on="content_url", how="inner")
        .join(users_df, on="user_id", how="inner")
        .sort([order_by, "dt"], descending=[True, descending])
    )

    count = len(contents)
    data = contents.slice(offset, limit).to_dicts()
    return dto.ContentResponse(count=count, data=data)


def match_keyword(keyword: str, row: tuple) -> bool:
    return keyword in f"{row[1]},{row[5]}".lower()  # title, tags


@router.get(
    "/community/trigger_messages",
    status_code=status.HTTP_200_OK,
    response_model=dto.TriggerMessageResponse,
)
async def fetch_trigger_messages(
    offset: int = 0,
    limit: int = Query(default=50, le=50),
    user_id: str | None = Query(default=None, description="유저의 슬랙 아이디"),
    search_word: str | None = Query(default=None, description="트리거 메시지 중 검색할 단어"),
    descending: bool = Query(default=True, description="내림차순 정렬 여부"),
    service: AppService = Depends(app_service),
) -> dto.TriggerMessageResponse:
    """조건에 맞는 트리거 메시지를 가져옵니다."""
    count, data = service.fetch_trigger_messages(
        offset=offset,
        limit=limit,
        user_id=user_id,
        search_word=search_word,
        descending=descending,
    )
    return dto.TriggerMessageResponse(count=count, data=data)


@router.get(
    "/community/archive_messages",
    status_code=status.HTTP_200_OK,
    response_model=dto.ArchiveMessageResponse,
)
async def fetch_archive_messages(
    offset: int = 0,
    limit: int = Query(default=50, le=50),
    ts: str | None = Query(default=None, description="메시지 생성 타임스탬프"),
    user_id: str | None = Query(default=None, description="유저의 슬랙 아이디"),
    search_word: str | None = Query(default=None, description="아카이브 메시지 중 검색할 단어"),
    trigger_word: str | None = Query(default=None, description="트리거 단어"),
    order_by: ArchiveMessageSortEnum = Query(
        default=ArchiveMessageSortEnum.TS, description="정렬 기준"
    ),
    descending: bool = Query(default=True, description="내림차순 정렬 여부"),
    exclude_emoji: bool = Query(default=True, description="이모지 제외 여부"),
    service: AppService = Depends(app_service),
) -> dto.ArchiveMessageResponse:
    """조건에 맞는 아카이브 메시지를 가져옵니다."""
    count, data = service.fetch_archive_messages(
        offset=offset,
        limit=limit,
        ts=ts,
        user_id=user_id,
        search_word=search_word,
        trigger_word=trigger_word,
        order_by=order_by,
        descending=descending,
        exclude_emoji=exclude_emoji,
    )
    return dto.ArchiveMessageResponse(count=count, data=data)
