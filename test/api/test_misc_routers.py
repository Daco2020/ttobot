"""미니 라우터 묶음 테스트.

- POST /v1/send-messages         (관리자용 슬랙 메시지 일괄 전송)
- GET  /v1/inflearn/coupons      (인프런 쿠폰 목록 조회)
- GET  /v1/writing-participation (글쓰기 참여 신청 목록 조회)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import csv
import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from app.config import settings
from app.api.views import message as message_view


# ---------------------------------------------------------------------------
# POST /v1/send-messages
# ---------------------------------------------------------------------------


def _admin(factory):
    return factory.make_user(user_id=settings.ADMIN_IDS[0], name="관리자")


def _non_admin(factory):
    return factory.make_user(user_id="U_GUEST", name="일반유저")


@pytest.fixture
def slack_post(mocker: MockerFixture):
    """slack_app.client.chat_postMessage 를 mock."""
    return mocker.patch.object(
        message_view.slack_app.client, "chat_postMessage", new=AsyncMock()
    )


def test_send_messages_admin_posts_each_message(
    client: TestClient, auth_for, factory, slack_post
) -> None:
    """✅ admin → dto_list 의 각 항목으로 chat_postMessage 호출."""
    auth_for(_admin(factory))

    response = client.post(
        "/v1/send-messages",
        json=[
            {"channel_id": "C_A", "message": "안녕"},
            {"channel_id": "C_B", "message": "반가워"},
        ],
    )

    assert response.status_code == 200
    assert response.json() == {"message": "메시지를 보냈습니다."}
    assert slack_post.await_count == 2
    calls = slack_post.await_args_list
    assert calls[0].kwargs == {"channel": "C_A", "text": "안녕"}
    assert calls[1].kwargs == {"channel": "C_B", "text": "반가워"}


def test_send_messages_non_admin_returns_403(
    client: TestClient, auth_for, factory, slack_post
) -> None:
    """⚠️ admin 이 아닌 유저 → 403."""
    auth_for(_non_admin(factory))

    response = client.post(
        "/v1/send-messages",
        json=[{"channel_id": "C_A", "message": "안녕"}],
    )

    assert response.status_code == 403
    slack_post.assert_not_awaited()


def test_send_messages_empty_list_returns_200_with_no_calls(
    client: TestClient, auth_for, factory, slack_post
) -> None:
    """🌀 dto_list 가 빈 리스트 → 200 + slack 호출 0회."""
    auth_for(_admin(factory))

    response = client.post("/v1/send-messages", json=[])

    assert response.status_code == 200
    slack_post.assert_not_awaited()


def test_send_messages_without_token_returns_403(
    client: TestClient, slack_post
) -> None:
    """⚠️ 인증 누락 → 403."""
    response = client.post(
        "/v1/send-messages",
        json=[{"channel_id": "C_A", "message": "hi"}],
    )
    assert response.status_code == 403
    slack_post.assert_not_awaited()


# ---------------------------------------------------------------------------
# GET /v1/inflearn/coupons
# ---------------------------------------------------------------------------


def _write_inflearn_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["code", "expired_at"], quoting=csv.QUOTE_ALL
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_inflearn_coupons_admin_returns_data(
    client: TestClient, auth_for, factory, tmp_store
) -> None:
    """✅ admin → CSV 행을 그대로 dict 리스트로 반환."""
    auth_for(_admin(factory))
    _write_inflearn_csv(
        tmp_store / "_inflearn_coupon.csv",
        [
            {"code": "ABC123", "expired_at": "2025-12-31"},
            {"code": "XYZ789", "expired_at": "2025-06-30"},
        ],
    )

    response = client.get("/v1/inflearn/coupons")

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == [
        {"code": "ABC123", "expired_at": "2025-12-31"},
        {"code": "XYZ789", "expired_at": "2025-06-30"},
    ]


def test_inflearn_coupons_non_admin_returns_403(
    client: TestClient, auth_for, factory, tmp_store
) -> None:
    """⚠️ admin 이 아닌 유저 → 403."""
    auth_for(_non_admin(factory))

    response = client.get("/v1/inflearn/coupons")

    assert response.status_code == 403


def test_inflearn_coupons_empty_csv_returns_empty_list(
    client: TestClient, auth_for, factory, tmp_store
) -> None:
    """🌀 CSV 가 헤더만 있을 때 빈 리스트."""
    auth_for(_admin(factory))
    _write_inflearn_csv(tmp_store / "_inflearn_coupon.csv", rows=[])

    response = client.get("/v1/inflearn/coupons")

    assert response.status_code == 200
    assert response.json() == {"data": []}


def test_inflearn_coupons_without_token_returns_403(
    client: TestClient, tmp_store
) -> None:
    """⚠️ 인증 누락 → 403."""
    response = client.get("/v1/inflearn/coupons")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /v1/writing-participation
# ---------------------------------------------------------------------------


def _write_writing_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["user_id", "name", "created_at", "is_writing_participation"],
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_writing_participation_returns_rows_as_dicts(
    client: TestClient, tmp_store
) -> None:
    """✅ CSV 행을 dict 리스트로 반환 (인증 불필요)."""
    _write_writing_csv(
        tmp_store / "writing_participation.csv",
        [
            {
                "user_id": "U_A",
                "name": "가나",
                "created_at": "2025-01-01 09:00:00",
                "is_writing_participation": "True",
            },
            {
                "user_id": "U_B",
                "name": "다라",
                "created_at": "2025-01-02 09:00:00",
                "is_writing_participation": "True",
            },
        ],
    )

    response = client.get("/v1/writing-participation")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["user_id"] == "U_A"
    assert data[1]["name"] == "다라"


def test_writing_participation_empty_csv_returns_empty_list(
    client: TestClient, tmp_store
) -> None:
    """🌀 CSV 가 헤더만 있을 때 빈 리스트."""
    _write_writing_csv(tmp_store / "writing_participation.csv", rows=[])

    response = client.get("/v1/writing-participation")

    assert response.status_code == 200
    assert response.json() == []
