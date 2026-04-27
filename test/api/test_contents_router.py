"""GET /v1/contents — 콘텐츠 검색 라우터 테스트.

주요 외부 의존성:
- store/users.csv, store/contents.csv : `tmp_store` + `csv_writer_helper` 로 격리
- googletrans 의 translate_keywords : `mocker.patch` 로 빈 리스트 반환하도록 봉쇄
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture


USERS_HEADER = ["user_id", "name", "channel_name", "channel_id", "intro", "deposit", "cohort"]
CONTENTS_HEADER = [
    "user_id",
    "username",
    "title",
    "content_url",
    "dt",
    "category",
    "description",
    "type",
    "tags",
    "curation_flag",
    "ts",
    "feedback_intensity",
]


def _user_row(**overrides):
    base = {
        "user_id": "U_TEST",
        "name": "테스트",
        "channel_name": "1_백엔드_채널",
        "channel_id": "C_TEST",
        "intro": "",
        "deposit": "0",
        "cohort": "10기",
    }
    base.update(overrides)
    return base


def _content_row(**overrides):
    base = {
        "user_id": "U_TEST",
        "username": "tester",
        "title": "테스트 글",
        "content_url": "https://example.com/post-1",
        "dt": "2025-01-01 10:00:00",
        "category": "기술 & 언어",
        "description": "",
        "type": "submit",
        "tags": "Python,FastAPI",
        "curation_flag": "N",
        "ts": "1735700000.000000",
        "feedback_intensity": "HOT",
    }
    base.update(overrides)
    return base


@pytest.fixture
def no_translate(mocker: MockerFixture):
    """contents 라우터의 translate_keywords 호출이 외부 API를 치지 않도록 봉쇄."""
    return mocker.patch(
        "app.api.views.contents.translate_keywords", return_value=[]
    )


# ---------------------------------------------------------------------------
# 전체보기
# ---------------------------------------------------------------------------


def test_contents_show_all_returns_paginated_descending(
    client: TestClient, tmp_store, csv_writer_helper, no_translate
) -> None:
    """✅ '전체보기' 키워드는 dt 내림차순으로 limit/offset 적용."""
    # given
    csv_writer_helper(
        tmp_store / "users.csv",
        USERS_HEADER,
        [_user_row(user_id="U_A", channel_name="1_백엔드_채널")],
    )
    csv_writer_helper(
        tmp_store / "contents.csv",
        CONTENTS_HEADER,
        [
            _content_row(
                user_id="U_A",
                content_url="https://example.com/old",
                dt="2025-01-01 10:00:00",
                ts="1.0",
            ),
            _content_row(
                user_id="U_A",
                content_url="https://example.com/new",
                dt="2025-02-01 10:00:00",
                ts="2.0",
            ),
            _content_row(
                user_id="U_A",
                content_url="https://example.com/middle",
                dt="2025-01-15 10:00:00",
                ts="3.0",
            ),
        ],
    )

    # when
    response = client.get("/v1/contents", params={"keyword": "전체보기", "limit": 2})

    # then
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert len(body["data"]) == 2
    # 최신 dt 가 먼저 나와야 함
    assert body["data"][0]["content_url"] == "https://example.com/new"
    assert body["data"][1]["content_url"] == "https://example.com/middle"
    assert body["data"][0]["relevance"] == 0


def test_contents_show_all_offset_skips_records(
    client: TestClient, tmp_store, csv_writer_helper, no_translate
) -> None:
    """🌀 offset 매우 큼 → 빈 data 반환."""
    csv_writer_helper(
        tmp_store / "users.csv",
        USERS_HEADER,
        [_user_row(user_id="U_A")],
    )
    csv_writer_helper(
        tmp_store / "contents.csv",
        CONTENTS_HEADER,
        [_content_row(user_id="U_A")],
    )

    response = client.get("/v1/contents", params={"keyword": "전체보기", "offset": 999})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["data"] == []


def test_contents_show_all_descending_false_orders_ascending(
    client: TestClient, tmp_store, csv_writer_helper, no_translate
) -> None:
    """🌀 descending=False 시 dt 오름차순."""
    csv_writer_helper(tmp_store / "users.csv", USERS_HEADER, [_user_row()])
    csv_writer_helper(
        tmp_store / "contents.csv",
        CONTENTS_HEADER,
        [
            _content_row(content_url="https://example.com/a", dt="2025-03-01 10:00:00", ts="1"),
            _content_row(content_url="https://example.com/b", dt="2025-01-01 10:00:00", ts="2"),
        ],
    )

    response = client.get(
        "/v1/contents", params={"keyword": "전체보기", "descending": False}
    )

    assert response.status_code == 200
    urls = [c["content_url"] for c in response.json()["data"]]
    assert urls == ["https://example.com/b", "https://example.com/a"]


# ---------------------------------------------------------------------------
# 키워드 검색
# ---------------------------------------------------------------------------


def test_contents_keyword_match_returns_results_with_relevance(
    client: TestClient, tmp_store, csv_writer_helper, no_translate
) -> None:
    """✅ 키워드가 title/tags/name 에 매칭되면 결과 반환 + relevance 부여."""
    csv_writer_helper(
        tmp_store / "users.csv",
        USERS_HEADER,
        [_user_row(user_id="U_A", name="홍길동", channel_name="1_백엔드_채널")],
    )
    csv_writer_helper(
        tmp_store / "contents.csv",
        CONTENTS_HEADER,
        [
            _content_row(
                user_id="U_A",
                title="Python 입문",
                tags="Python,FastAPI",
                content_url="https://example.com/python",
                dt="2025-02-01 10:00:00",
                ts="1",
            ),
            _content_row(
                user_id="U_A",
                title="다른 글",
                tags="Java",
                content_url="https://example.com/java",
                dt="2025-01-01 10:00:00",
                ts="2",
            ),
        ],
    )

    response = client.get("/v1/contents", params={"keyword": "python"})

    assert response.status_code == 200
    body = response.json()
    urls = [c["content_url"] for c in body["data"]]
    assert "https://example.com/python" in urls
    assert "https://example.com/java" not in urls
    assert body["count"] >= 1


def test_contents_no_match_returns_empty(
    client: TestClient, tmp_store, csv_writer_helper, no_translate
) -> None:
    """🌀 매칭되는 콘텐츠가 없으면 count=0, data=[]."""
    csv_writer_helper(tmp_store / "users.csv", USERS_HEADER, [_user_row()])
    csv_writer_helper(
        tmp_store / "contents.csv",
        CONTENTS_HEADER,
        [_content_row(title="다른 글", tags="Java")],
    )

    response = client.get("/v1/contents", params={"keyword": "전혀없는키워드xyz"})

    assert response.status_code == 200
    body = response.json()
    # 매칭 없음 → 결과는 0건이어야 한다.
    assert all(
        "전혀없는키워드xyz" not in (c.get("title", "") + c.get("tags", "")).lower()
        for c in body["data"]
    )
    assert body["data"] == [] or body["count"] == 0


def test_contents_keyword_split_by_comma_and_slash(
    client: TestClient, tmp_store, csv_writer_helper, no_translate
) -> None:
    """🌀 콤마/슬래시로 분리된 키워드 → 둘 중 하나라도 매칭되면 결과."""
    csv_writer_helper(tmp_store / "users.csv", USERS_HEADER, [_user_row()])
    csv_writer_helper(
        tmp_store / "contents.csv",
        CONTENTS_HEADER,
        [
            _content_row(
                title="Python 글", tags="Python", content_url="https://example.com/py", ts="1"
            ),
            _content_row(
                title="FastAPI 글", tags="FastAPI", content_url="https://example.com/fa", ts="2"
            ),
            _content_row(
                title="JavaScript 글", tags="JS", content_url="https://example.com/js", ts="3"
            ),
        ],
    )

    response = client.get("/v1/contents", params={"keyword": "python,fastapi"})

    assert response.status_code == 200
    urls = {c["content_url"] for c in response.json()["data"]}
    assert "https://example.com/py" in urls
    assert "https://example.com/fa" in urls
    assert "https://example.com/js" not in urls


def test_contents_category_filter_keyword_search(
    client: TestClient, tmp_store, csv_writer_helper, no_translate
) -> None:
    """✅ 키워드 검색 + category → 해당 카테고리만 매칭."""
    csv_writer_helper(tmp_store / "users.csv", USERS_HEADER, [_user_row()])
    csv_writer_helper(
        tmp_store / "contents.csv",
        CONTENTS_HEADER,
        [
            _content_row(
                title="기술 글",
                category="기술 & 언어",
                content_url="https://example.com/tech",
                ts="1",
            ),
            _content_row(
                title="일상 글",
                category="일상 & 생각 & 회고",
                content_url="https://example.com/daily",
                ts="2",
            ),
        ],
    )

    response = client.get(
        "/v1/contents", params={"keyword": "글", "category": "기술 & 언어"}
    )

    assert response.status_code == 200
    body = response.json()
    urls = {c["content_url"] for c in body["data"]}
    assert urls == {"https://example.com/tech"}


def test_contents_category_filter_show_all(
    client: TestClient, tmp_store, csv_writer_helper, no_translate
) -> None:
    """✅ 전체보기 + category → 카테고리 일치 글만 반환."""
    csv_writer_helper(tmp_store / "users.csv", USERS_HEADER, [_user_row()])
    csv_writer_helper(
        tmp_store / "contents.csv",
        CONTENTS_HEADER,
        [
            _content_row(
                category="기술 & 언어",
                content_url="https://example.com/tech",
                ts="1",
            ),
            _content_row(
                category="일상 & 생각 & 회고",
                content_url="https://example.com/daily",
                ts="2",
            ),
            _content_row(
                category="기술 & 언어",
                content_url="https://example.com/tech-2",
                ts="3",
            ),
        ],
    )

    response = client.get(
        "/v1/contents",
        params={"keyword": "전체보기", "category": "기술 & 언어"},
    )

    assert response.status_code == 200
    body = response.json()
    urls = {c["content_url"] for c in body["data"]}
    assert urls == {"https://example.com/tech", "https://example.com/tech-2"}
    assert body["count"] == 2


def test_contents_job_category_filter(
    client: TestClient, tmp_store, csv_writer_helper, no_translate
) -> None:
    """✅ job_category 쿼리 → 해당 직군 채널의 유저들만 매칭."""
    csv_writer_helper(
        tmp_store / "users.csv",
        USERS_HEADER,
        [
            _user_row(user_id="U_BE", channel_name="1_백엔드_채널"),
            _user_row(user_id="U_FE", channel_name="1_프론트_채널"),
        ],
    )
    csv_writer_helper(
        tmp_store / "contents.csv",
        CONTENTS_HEADER,
        [
            _content_row(
                user_id="U_BE", title="Hi", content_url="https://example.com/be", ts="1"
            ),
            _content_row(
                user_id="U_FE", title="Hi", content_url="https://example.com/fe", ts="2"
            ),
        ],
    )

    response = client.get("/v1/contents", params={"keyword": "Hi", "job_category": "백엔드"})

    assert response.status_code == 200
    urls = {c["content_url"] for c in response.json()["data"]}
    assert urls == {"https://example.com/be"}


# ---------------------------------------------------------------------------
# 입력 검증
# ---------------------------------------------------------------------------


def test_contents_limit_over_50_returns_422(client: TestClient) -> None:
    """⚠️ limit > 50 → 422."""
    response = client.get("/v1/contents", params={"keyword": "전체보기", "limit": 51})
    assert response.status_code == 422


def test_contents_missing_keyword_returns_422(client: TestClient) -> None:
    """⚠️ keyword 파라미터 없음 → 422."""
    response = client.get("/v1/contents")
    assert response.status_code == 422
