"""POST /v1/points — 관리자 포인트 지급 라우터 테스트.

외부 의존성:
- point_service (override_point_service 로 mock)
- send_point_noti_message + slack_app.client (mocker.patch 로 봉쇄)
- asyncio.sleep (실제 1초 대기를 막기 위해 mock)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from app.config import settings
from app.api.views import point as point_view


def _admin_user(factory):
    return factory.make_user(user_id=settings.ADMIN_IDS[0], name="관리자")


def _non_admin_user(factory):
    return factory.make_user(user_id="U_GUEST", name="일반유저")


@pytest.fixture
def no_sleep(mocker: MockerFixture):
    """asyncio.sleep(1) 호출이 테스트 시간을 잡아먹지 않도록 봉쇄."""
    return mocker.patch("app.api.views.point.asyncio.sleep", new=AsyncMock())


@pytest.fixture
def send_noti_mock(mocker: MockerFixture):
    """send_point_noti_message 호출을 mock 으로 가로챈다."""
    return mocker.patch(
        "app.api.views.point.send_point_noti_message", new=AsyncMock()
    )


@pytest.fixture
def slack_client_mock(mocker: MockerFixture):
    """slack_app.client 가 직접 호출되지 않더라도 import 시 안전하도록 mock 메서드만 깔아둔다."""
    client = point_view.slack_app.client
    mocker.patch.object(client, "chat_postMessage")
    return client


# ---------------------------------------------------------------------------
# curation
# ---------------------------------------------------------------------------


def test_grant_points_curation_calls_service_per_user(
    client: TestClient,
    auth_for,
    factory,
    override_point_service,
    no_sleep,
    send_noti_mock,
    slack_client_mock,
) -> None:
    """✅ point_type=curation → 유저마다 grant_if_curation_selected + 알림 메시지."""
    auth_for(_admin_user(factory))
    service = MagicMock()
    service.grant_if_curation_selected.side_effect = lambda uid: f"{uid} 큐레이션 선정"
    override_point_service(service)

    response = client.post(
        "/v1/points",
        params={"point_type": "curation", "text": "축하"},
        json=["U_A", "U_B"],
    )

    assert response.status_code == 200
    assert response.json() == {"message": "큐레이션 선정 포인트를 지급했습니다."}
    assert service.grant_if_curation_selected.call_count == 2
    service.grant_if_curation_selected.assert_any_call("U_A")
    service.grant_if_curation_selected.assert_any_call("U_B")
    assert send_noti_mock.await_count == 2
    # 첫 번째 호출 내용 확인 (text 가 prefix 로 들어가야 한다)
    first_kwargs = send_noti_mock.await_args_list[0].kwargs
    assert first_kwargs["channel"] == "U_A"
    assert "축하" in first_kwargs["text"]
    assert "큐레이션 선정" in first_kwargs["text"]


def test_grant_points_curation_with_empty_user_ids(
    client: TestClient,
    auth_for,
    factory,
    override_point_service,
    no_sleep,
    send_noti_mock,
    slack_client_mock,
) -> None:
    """🌀 user_ids 가 빈 리스트 → 200 + 호출 0회."""
    auth_for(_admin_user(factory))
    service = MagicMock()
    override_point_service(service)

    response = client.post(
        "/v1/points",
        params={"point_type": "curation"},
        json=[],
    )

    assert response.status_code == 200
    service.grant_if_curation_selected.assert_not_called()
    send_noti_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# village_conference
# ---------------------------------------------------------------------------


def test_grant_points_village_conference_calls_service_per_user(
    client: TestClient,
    auth_for,
    factory,
    override_point_service,
    no_sleep,
    send_noti_mock,
    slack_client_mock,
) -> None:
    """✅ point_type=village_conference → 유저마다 grant_if_village_conference_participated."""
    auth_for(_admin_user(factory))
    service = MagicMock()
    service.grant_if_village_conference_participated.side_effect = (
        lambda uid: f"{uid} 반상회"
    )
    override_point_service(service)

    response = client.post(
        "/v1/points",
        params={"point_type": "village_conference"},
        json=["U_A"],
    )

    assert response.status_code == 200
    assert response.json() == {"message": "빌리지 반상회 참여 포인트를 지급했습니다."}
    service.grant_if_village_conference_participated.assert_called_once_with("U_A")


# ---------------------------------------------------------------------------
# special
# ---------------------------------------------------------------------------


def test_grant_points_special_with_point_and_reason(
    client: TestClient,
    auth_for,
    factory,
    override_point_service,
    no_sleep,
    send_noti_mock,
    slack_client_mock,
) -> None:
    """✅ point_type=special + point/reason → 유저별 grant_if_special_point 호출."""
    auth_for(_admin_user(factory))
    service = MagicMock()
    service.grant_if_special_point.side_effect = (
        lambda uid, p, r: f"{uid}/{p}/{r}"
    )
    override_point_service(service)

    response = client.post(
        "/v1/points",
        params={
            "point_type": "special",
            "point": 50,
            "reason": "특별 기여",
        },
        json=["U_A"],
    )

    assert response.status_code == 200
    assert response.json() == {"message": "특별 포인트를 지급했습니다."}
    service.grant_if_special_point.assert_called_once_with("U_A", 50, "특별 기여")


def test_grant_points_special_without_point_returns_400(
    client: TestClient,
    auth_for,
    factory,
    override_point_service,
    no_sleep,
    send_noti_mock,
    slack_client_mock,
) -> None:
    """⚠️ special 인데 point=0 → 400."""
    auth_for(_admin_user(factory))
    service = MagicMock()
    override_point_service(service)

    response = client.post(
        "/v1/points",
        params={"point_type": "special", "point": 0, "reason": "x"},
        json=["U_A"],
    )

    assert response.status_code == 400
    assert "point와 reason" in response.json()["detail"]
    service.grant_if_special_point.assert_not_called()


def test_grant_points_special_without_reason_returns_400(
    client: TestClient,
    auth_for,
    factory,
    override_point_service,
    no_sleep,
    send_noti_mock,
    slack_client_mock,
) -> None:
    """⚠️ special 인데 reason 빈 문자열 → 400."""
    auth_for(_admin_user(factory))
    service = MagicMock()
    override_point_service(service)

    response = client.post(
        "/v1/points",
        params={"point_type": "special", "point": 100, "reason": ""},
        json=["U_A"],
    )

    assert response.status_code == 400
    service.grant_if_special_point.assert_not_called()


# ---------------------------------------------------------------------------
# 권한
# ---------------------------------------------------------------------------


def test_grant_points_non_admin_returns_403(
    client: TestClient,
    auth_for,
    factory,
    override_point_service,
    no_sleep,
    send_noti_mock,
    slack_client_mock,
) -> None:
    """⚠️ admin 이 아닌 유저 → 403."""
    auth_for(_non_admin_user(factory))
    service = MagicMock()
    override_point_service(service)

    response = client.post(
        "/v1/points",
        params={"point_type": "curation"},
        json=["U_A"],
    )

    assert response.status_code == 403
    service.grant_if_curation_selected.assert_not_called()


def test_grant_points_without_token_returns_403(client: TestClient) -> None:
    """⚠️ 인증 누락 → 403."""
    response = client.post(
        "/v1/points",
        params={"point_type": "curation"},
        json=["U_A"],
    )
    assert response.status_code == 403
