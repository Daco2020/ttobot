from enum import StrEnum
from typing import Any, Literal
import polars as pl

from starlette import status
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.auth import current_user
from app.constants import ContentCategoryEnum, ContentSortEnum
from app.api import dto
from app.models import SimpleUser
from app.utils import translate_keywords
from app.config import settings
from app.slack.event_handler import app as slack_app
from slack_sdk.errors import SlackApiError


class JobCategoryEnum(StrEnum):
    DATA_SCIENCE = "데이터과학"
    DATA_ANALYSIS = "데이터분석"
    DATA_ENGINEERING = "데이터엔지니어"
    BACKEND = "백엔드"
    ANDROID = "안드"
    INFRA = "인프라"
    FULL_STACK = "풀스택"
    FRONTEND = "프론트"
    FLUTTER = "플러터"
    AI = "ai"
    IOS = "ios"
    ML = "ml"
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
    job_category: JobCategoryEnum | None = None,
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

    # 직군 필터링
    if job_category:
        users_df = (
            users_df.filter(pl.col("channel_name").str.contains(f"(?i){job_category}"))
            .with_columns(pl.lit(job_category).alias("job_category"))
            .drop("channel_name")
        )
    else:
        job_categories = [category.value for category in JobCategoryEnum]
        users_df = users_df.with_columns(
            pl.col("channel_name")
            .apply(lambda x: next((cat for cat in job_categories if cat in x), None))
            .alias("job_category")
        ).drop("channel_name")

    # 유니크한 콘텐츠만 가져오기
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


@router.get(
    "/messages",
    status_code=status.HTTP_200_OK,
)
async def get_message(
    ts: str,
    channel_id: str,
    type: Literal["message", "reply"] = "message",
    user: SimpleUser = Depends(current_user),
) -> dict[str, Any]:
    if user.user_id not in settings.ADMIN_IDS:
        raise HTTPException(status_code=403, detail="수정 권한이 없습니다.")

    try:
        if type == "message":
            data = await slack_app.client.conversations_history(
                channel=channel_id, latest=ts, inclusive=True, limit=1
            )

        else:
            data = await slack_app.client.conversations_replies(
                channel=channel_id, ts=ts, inclusive=True, limit=1
            )

        message = next((msg for msg in data["messages"] if msg["ts"] == ts), None)
        if not message:
            raise HTTPException(status_code=404, detail="콘텐츠를 찾을 수 없습니다.")

        text = message["text"]
        blocks = message["blocks"]
        attachments = message.get("attachments", [])

        return {
            "text": text,
            "blocks": blocks,
            "attachments": attachments,
        }

    except SlackApiError as e:
        raise HTTPException(status_code=409, detail=str(e))


class UpdateMessageRequest(dto.BaseModel):
    text: str
    blocks: list[dict[str, Any]]
    attachments: list[dict[str, Any]]


@router.post(
    "/messages",
    status_code=status.HTTP_200_OK,
)
async def update_message(
    password: str,
    ts: str,
    channel_id: str,
    data: UpdateMessageRequest,
    user: SimpleUser = Depends(current_user),
):
    if user.user_id not in settings.ADMIN_IDS:
        raise HTTPException(status_code=403, detail="수정 권한이 없습니다.")

    if password != settings.SECRET_KEY:
        raise HTTPException(status_code=403, detail="비밀번호가 일치하지 않습니다.")

    try:
        await slack_app.client.chat_update(
            channel=channel_id,
            ts=ts,
            text=data.text,
            blocks=data.blocks,
            attachments=data.attachments,
        )

        permalink_res = await slack_app.client.chat_getPermalink(
            channel=channel_id,
            message_ts=ts,
        )

        return {"permalink": permalink_res["permalink"]}

    except SlackApiError as e:
        raise HTTPException(status_code=409, detail=str(e))
