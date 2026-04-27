"""POST/GET /v1/paper-planes 라우터 테스트.

ApiService 자체는 별도 파일에서 단위 테스트한다. 본 파일은 라우터 분기와 권한만 검증한다.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import settings
from app.constants import BOT_IDS
from test import factories


# ---------------------------------------------------------------------------
# POST /v1/paper-planes
# ---------------------------------------------------------------------------


def test_send_paper_plane_success_returns_201(
    client: TestClient, auth_for, factory, override_api_service
) -> None:
    """✅ 정상 발송 → 201 + service.send_paper_plane 호출."""
    auth_for(factory.make_user(user_id="U_SENDER", name="발신자"))
    service = MagicMock()
    service.send_paper_plane = AsyncMock(return_value=factories.make_paper_plane())
    override_api_service(service)

    response = client.post(
        "/v1/paper-planes",
        json={"receiver_id": "U_RECEIVER", "text": "감사합니다."},
    )

    assert response.status_code == 201
    assert response.json() == {"message": "종이비행기를 보냈습니다."}
    service.send_paper_plane.assert_awaited_once()
    kwargs = service.send_paper_plane.await_args.kwargs
    assert kwargs["sender_id"] == "U_SENDER"
    assert kwargs["sender_name"] == "발신자"
    assert kwargs["receiver_id"] == "U_RECEIVER"
    assert kwargs["text"] == "감사합니다."


def test_send_paper_plane_to_self_returns_400(
    client: TestClient, auth_for, factory, override_api_service
) -> None:
    """⚠️ 자기 자신에게 발송 → 400."""
    auth_for(factory.make_user(user_id="U_ME"))
    service = MagicMock()
    service.send_paper_plane = AsyncMock()
    override_api_service(service)

    response = client.post(
        "/v1/paper-planes",
        json={"receiver_id": "U_ME", "text": "안녕"},
    )

    assert response.status_code == 400
    assert "자신에게 보낼 수 없어요" in response.json()["detail"]
    service.send_paper_plane.assert_not_called()


def test_send_paper_plane_text_over_300_returns_400(
    client: TestClient, auth_for, factory, override_api_service
) -> None:
    """⚠️ 텍스트가 300자를 초과 → 400."""
    auth_for(factory.make_user(user_id="U_SENDER"))
    service = MagicMock()
    service.send_paper_plane = AsyncMock()
    override_api_service(service)

    response = client.post(
        "/v1/paper-planes",
        json={"receiver_id": "U_RECEIVER", "text": "x" * 301},
    )

    assert response.status_code == 400
    assert "300자 이내" in response.json()["detail"]
    service.send_paper_plane.assert_not_called()


def test_send_paper_plane_text_exactly_300_succeeds(
    client: TestClient, auth_for, factory, override_api_service
) -> None:
    """🌀 정확히 300자 → 통과."""
    auth_for(factory.make_user(user_id="U_SENDER"))
    service = MagicMock()
    service.send_paper_plane = AsyncMock(return_value=factories.make_paper_plane())
    override_api_service(service)

    response = client.post(
        "/v1/paper-planes",
        json={"receiver_id": "U_RECEIVER", "text": "x" * 300},
    )

    assert response.status_code == 201
    service.send_paper_plane.assert_awaited_once()


def test_send_paper_plane_to_bot_returns_400(
    client: TestClient, auth_for, factory, override_api_service
) -> None:
    """⚠️ receiver_id 가 BOT_IDS 에 포함 → 400."""
    auth_for(factory.make_user(user_id="U_SENDER"))
    service = MagicMock()
    service.send_paper_plane = AsyncMock()
    override_api_service(service)

    response = client.post(
        "/v1/paper-planes",
        json={"receiver_id": BOT_IDS[0], "text": "안녕"},
    )

    assert response.status_code == 400
    assert "봇에게" in response.json()["detail"]
    service.send_paper_plane.assert_not_called()


def test_send_paper_plane_when_service_raises_404_propagates(
    client: TestClient, auth_for, factory, override_api_service
) -> None:
    """⚠️ service 단에서 receiver 못 찾으면 HTTPException(404) → 클라이언트도 404."""
    auth_for(factory.make_user(user_id="U_SENDER"))
    service = MagicMock()
    service.send_paper_plane = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="받는 사람을 찾을 수 없어요. 😢")
    )
    override_api_service(service)

    response = client.post(
        "/v1/paper-planes",
        json={"receiver_id": "U_GHOST", "text": "안녕"},
    )

    assert response.status_code == 404
    assert "받는 사람을 찾을 수 없어요" in response.json()["detail"]


def test_send_paper_plane_without_token_returns_403(client: TestClient) -> None:
    """⚠️ 인증 누락 → 403."""
    response = client.post(
        "/v1/paper-planes",
        json={"receiver_id": "U_X", "text": "hi"},
    )
    assert response.status_code == 403


def test_send_paper_plane_super_admin_passes_through(
    client: TestClient, auth_for, factory, override_api_service
) -> None:
    """🌀 SUPER_ADMIN 발신자도 동일하게 처리된다.

    현재 로직은 super_admin 분기와 일반 분기가 모두 `pass` 라 실질적 차이는 없지만,
    분기 자체를 통과해 service 까지 도달하는지 확인한다.
    """
    auth_for(factory.make_user(user_id=settings.SUPER_ADMIN, name="슈퍼"))
    service = MagicMock()
    service.send_paper_plane = AsyncMock(return_value=factories.make_paper_plane())
    override_api_service(service)

    response = client.post(
        "/v1/paper-planes",
        json={"receiver_id": "U_RECEIVER", "text": "hi"},
    )

    assert response.status_code == 201
    service.send_paper_plane.assert_awaited_once()


# ---------------------------------------------------------------------------
# GET /v1/paper-planes/sent
# ---------------------------------------------------------------------------


def test_fetch_sent_paper_planes_returns_list(
    client: TestClient, auth_for, factory, override_api_service
) -> None:
    """✅ 보낸 종이비행기 + 페이지네이션."""
    auth_for(factory.make_user(user_id="U_SENDER"))
    plane_a = factories.make_paper_plane(sender_id="U_SENDER", receiver_id="U_A")
    plane_b = factories.make_paper_plane(sender_id="U_SENDER", receiver_id="U_B")
    service = MagicMock()
    service.fetch_sent_paper_planes.return_value = (2, [plane_a, plane_b])
    override_api_service(service)

    response = client.get("/v1/paper-planes/sent", params={"offset": 0, "limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert len(body["data"]) == 2
    assert body["data"][0]["receiver_id"] == "U_A"
    service.fetch_sent_paper_planes.assert_called_once_with(
        user_id="U_SENDER", offset=0, limit=10
    )


def test_fetch_sent_paper_planes_without_token_returns_403(client: TestClient) -> None:
    """⚠️ 인증 누락 → 403."""
    response = client.get("/v1/paper-planes/sent")
    assert response.status_code == 403


def test_fetch_sent_paper_planes_limit_over_1000_returns_422(
    client: TestClient, auth_for, factory
) -> None:
    """🌀 limit > 1000 → 422 (Query 검증)."""
    auth_for(factory.make_user(user_id="U_SENDER"))

    response = client.get(
        "/v1/paper-planes/sent", params={"offset": 0, "limit": 1001}
    )

    assert response.status_code == 422


def test_fetch_sent_paper_planes_huge_offset_returns_empty(
    client: TestClient, auth_for, factory, override_api_service
) -> None:
    """🌀 offset 매우 큼 → service 가 빈 리스트 반환, count 는 그대로."""
    auth_for(factory.make_user(user_id="U_SENDER"))
    service = MagicMock()
    service.fetch_sent_paper_planes.return_value = (5, [])  # 전체 5개, 현재 페이지 0개
    override_api_service(service)

    response = client.get(
        "/v1/paper-planes/sent", params={"offset": 9999, "limit": 100}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 5
    assert body["data"] == []


# ---------------------------------------------------------------------------
# GET /v1/paper-planes/received
# ---------------------------------------------------------------------------


def test_fetch_received_paper_planes_returns_list(
    client: TestClient, auth_for, factory, override_api_service
) -> None:
    """✅ 받은 종이비행기."""
    auth_for(factory.make_user(user_id="U_RECEIVER"))
    plane = factories.make_paper_plane(sender_id="U_X", receiver_id="U_RECEIVER")
    service = MagicMock()
    service.fetch_received_paper_planes.return_value = (1, [plane])
    override_api_service(service)

    response = client.get("/v1/paper-planes/received", params={"offset": 0, "limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["data"][0]["sender_id"] == "U_X"
    service.fetch_received_paper_planes.assert_called_once_with(
        user_id="U_RECEIVER", offset=0, limit=10
    )


def test_fetch_received_paper_planes_without_token_returns_403(
    client: TestClient,
) -> None:
    """⚠️ 인증 누락 → 403."""
    response = client.get("/v1/paper-planes/received")
    assert response.status_code == 403
