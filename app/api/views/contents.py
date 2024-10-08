from enum import StrEnum
import polars as pl

from starlette import status
from fastapi import APIRouter, Query
from app.constants import ContentCategoryEnum, ContentSortEnum
from app.api import dto
from app.utils import translate_keywords


class JobCategoryEnum(StrEnum):
    DATA_SCIENCE = "데이터과학"
    DATA_ANALYSIS = "데이터분석"
    DATA_ENGINEERING = "데이터엔지니어"
    BACKEND = "백엔드"
    ANDROID = "안드로이드"
    INFRA = "인프라"
    FULL_STACK = "풀스택"
    FRONTEND = "프론트"
    FLUTTER = "플러터"
    AI_RESEARCH = "ai연구"
    IOS = "ios"
    ML_AI_ENGINEERING = "ml-ai-엔지니어"
    PMPO = "pmpo"


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
    # TODO: LIKE 컬럼 추가하기
    # TODO: 결과가 없을 경우, 글감 추천하기 <- 클라이언트가 처리
    # TODO: 북마크 글 연동하기
    # TODO: 큐레이션 탭 추가하기

    # 원본 데이터 불러오기
    users_df = pl.read_csv(
        "store/users.csv",
        columns=["user_id", "name", "cohort", "channel_name"],
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

    joined_df = contents_df.unique(subset=["content_url"]).join(
        users_df, on="user_id", how="inner"
    )

    if keyword == "전체보기":
        # '전체보기'는 최신순으로 정렬하여 반환
        contents = joined_df.sort(["dt"], descending=descending)
        count = len(contents)
        data = list(
            map(
                lambda x: {**x, "relevance": 0},
                contents.slice(offset, limit).to_dicts(),
            )
        )
        return dto.ContentResponse(count=count, data=data)

    if category:
        contents_df = contents_df.filter(contents_df["category"] == category)

    # 키워드 추출, TODO: 명사 단위로 쪼개서 검색하기
    keywords = [
        keyword.lower()
        for keyword in keyword.replace(",", " ").replace("/", " ").split(" ")
        if keyword
    ]
    keywords.extend(translate_keywords(keywords))

    # 키워드 매칭
    matched_dfs = [
        joined_df.filter(
            joined_df.apply(lambda row: match_keyword(keyword, row)).to_series()
        )
        for keyword in set(keywords)
    ]
    if not matched_dfs:
        return dto.ContentResponse(count=0, data=[])

    # 관련도 추가
    combined_df: pl.DataFrame = pl.concat(matched_dfs)
    grouped_df = combined_df.groupby("content_url").agg(pl.count().alias("relevance"))

    contents = joined_df.join(grouped_df, on="content_url", how="inner").sort(
        [order_by, "dt"], descending=[descending, True]
    )

    count = len(contents)
    data = contents.slice(offset, limit).to_dicts()
    return dto.ContentResponse(count=count, data=data)


def match_keyword(keyword: str, row: tuple) -> bool:
    return keyword in f"{row[1]},{row[5]},{row[7]}".lower()  # title, tags, name
