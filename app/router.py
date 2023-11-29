from enum import Enum
from typing import Any, TypedDict
import pandas as pd
from starlette import status
from fastapi import APIRouter
import googletrans
import re

router = APIRouter()
translator = googletrans.Translator()


class ContentSortEnum(str, Enum):
    DT = "dt"
    LIKE = "like"
    RELEVANCE = "relevance"


class Content(TypedDict):
    user_id: str
    name: str
    title: str
    content_url: str
    dt: str
    category: str
    tags: str


@router.get(
    "/contents",
    status_code=status.HTTP_200_OK,
)
async def fetch_contents(
    keyword: str,
    offset: int = 0,
    limit: int = 10,
    category: str = "",
    sort_by: ContentSortEnum = ContentSortEnum.DT,
    is_ascending: bool = False,
) -> list[Any]:
    """콘텐츠를 가져옵니다."""
    # TODO: 기수(period) 정보를 유저정보에 추가하기
    # TODO: LIKE 컬럼 추가하기
    # TODO: 결과가 없을 경우, 글감 추천하기

    # 원본 데이터 불러오기
    users_df = pd.read_csv(
        "store/users.csv", usecols=["user_id", "name"], keep_default_na=False
    )
    contents_df = pd.read_csv(
        "store/contents.csv",
        usecols=["user_id", "title", "content_url", "dt", "category", "tags"],
        keep_default_na=False,
    )

    # 키워드 추출, TODO: 명사 단위로 쪼개서 검색하기
    keywords = [
        keyword
        for keyword in keyword.replace(",", " ").replace("/", " ").split(" ")
        if keyword
    ]
    keywords.extend(translate_keywords(keywords))
    print(set(keywords))

    # 키워드 매칭
    matched_dfs = []
    for keyword in set(keywords):
        keyword_matched = contents_df.apply(
            lambda row: match_keyword(keyword, row),
            axis=1,
        )
        matched_dfs.append(contents_df[keyword_matched])

    # 관련도 추가
    combined_df = pd.concat(matched_dfs, ignore_index=True)
    combined_df["relevance"] = combined_df.groupby(["content_url"]).transform("size")

    # 중복 제거 및 병합
    unique_df = combined_df.drop_duplicates(subset=["content_url"], keep="first")
    merged_df = pd.merge(users_df, unique_df, on="user_id", how="inner")
    print(merged_df)

    # 정렬 및 페이징
    sorted_df = merged_df.sort_values(
        by=[sort_by, "dt"], ascending=[False, is_ascending]
    )
    paged_df = sorted_df.iloc[offset : offset + limit]
    contents: list[Content] = [record for record in paged_df.to_dict(orient="records")]
    return contents


def match_keyword(keyword: str, row: pd.Series) -> bool:
    return keyword in f"{row['title']},{row['tags']}".lower()


def translate_keywords(keywords: list[str]) -> list[str]:
    results = []
    for keyword in keywords:
        value = is_english(keyword)
        if value is True:
            # 영어 -> 한글 번역, 한글이 없는 단어는 그대로 영어가 나올 수 있음.
            results.append(translator.translate(keyword, dest="ko").text.lower())
        elif value is False:
            results.append(translator.translate(keyword, dest="en").text.lower())
        else:
            continue
    return results


def is_english(text):
    if re.match("^[a-zA-Z]+$", text):
        return True
    elif re.match("^[가-힣]+$", text):
        return False
    else:
        return None
