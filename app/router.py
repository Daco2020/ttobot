from typing import Any
import pandas as pd
from starlette import status
from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/contents",
    status_code=status.HTTP_200_OK,
)
async def fetch_contents(
    offset: int = 0,
    limit: int = 10,
) -> list[Any]:
    """콘텐츠를 가져옵니다."""
    users_df = pd.read_csv(
        "store/users.csv", usecols=["user_id", "name"], keep_default_na=False
    )
    contents_df = pd.read_csv("store/contents.csv", keep_default_na=False)
    merged_df = pd.merge(users_df, contents_df, on="user_id", how="inner")
    sorted_df = merged_df.sort_values(by="dt", ascending=False)
    result_df = sorted_df.iloc[offset : offset + limit]
    return [record for record in result_df.to_dict(orient="records")]
    # TODO: 기수 정보를 유저정보에 추가 핋요.
    # TODO: content type 이 pass 라면 제외한다.
    # TODO: 응답 dto 필요.
