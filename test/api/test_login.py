"""app/api/views/login.py 라우터 테스트.

대상 엔드포인트:
- GET  /v1/slack/login
- GET  /v1/slack/auth
- GET  /v1/slack/auth/refresh
- GET  /v1/slack/me
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from app.api.auth import encode_token
from app.api.views import login as login_view


# ---------------------------------------------------------------------------
# GET /v1/slack/login
# ---------------------------------------------------------------------------


def test_slack_login_returns_redirect_url(client: TestClient, mocker: MockerFixture) -> None:
    """✅ 정상 호출 시 redirect_url 을 응답한다."""
    # given - state 발급과 url 생성을 mock
    mocker.patch.object(login_view.oauth_flow, "issue_new_state", return_value="STATE_X")
    fake_generator = MagicMock()
    fake_generator.generate.return_value = "https://slack.example/oauth?state=STATE_X"
    mocker.patch.object(login_view.oauth_settings, "authorize_url_generator", fake_generator)

    # when
    response = client.get("/v1/slack/login")

    # then
    assert response.status_code == 200
    assert response.json() == {"redirect_url": "https://slack.example/oauth?state=STATE_X"}
    fake_generator.generate.assert_called_once_with(state="STATE_X")


# ---------------------------------------------------------------------------
# GET /v1/slack/auth
# ---------------------------------------------------------------------------


def test_slack_auth_with_valid_code_returns_tokens(
    client: TestClient, mocker: MockerFixture
) -> None:
    """✅ 정상 code → access/refresh 토큰 JSON 응답."""
    # given
    fake_result = MagicMock()
    fake_result.user_id = "U_OAUTH"
    mocker.patch.object(login_view.oauth_flow, "run_installation", return_value=fake_result)

    # when
    response = client.get("/v1/slack/auth", params={"code": "abc", "state": "STATE_X"})

    # then
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    # access_token은 type 키가 없고, refresh_token은 type=refresh 가 들어있어야 한다.
    from app.api.auth import decode_token

    access = decode_token(body["access_token"])
    refresh = decode_token(body["refresh_token"])
    assert access["user_id"] == "U_OAUTH"
    assert "type" not in access
    assert refresh["user_id"] == "U_OAUTH"
    assert refresh["type"] == "refresh"


def test_slack_auth_with_error_param_returns_404(client: TestClient) -> None:
    """⚠️ 슬랙이 error 쿼리를 반환한 경우 → 404."""
    # when
    response = client.get("/v1/slack/auth", params={"error": "access_denied"})

    # then
    assert response.status_code == 404
    assert "Slack OAuth Error" in response.json()["detail"]


def test_slack_auth_without_code_returns_403(client: TestClient) -> None:
    """⚠️ code 가 없으면 → 403."""
    # when
    response = client.get("/v1/slack/auth")

    # then
    assert response.status_code == 403
    assert "Invalid authentication code" in response.json()["detail"]


def test_slack_auth_when_run_installation_returns_none(
    client: TestClient, mocker: MockerFixture
) -> None:
    """⚠️ run_installation 이 None 을 반환하면 → 403."""
    # given
    mocker.patch.object(login_view.oauth_flow, "run_installation", return_value=None)

    # when
    response = client.get("/v1/slack/auth", params={"code": "abc"})

    # then
    assert response.status_code == 403
    assert "Failed to run installation" in response.json()["detail"]


# ---------------------------------------------------------------------------
# GET /v1/slack/auth/refresh
# ---------------------------------------------------------------------------


def test_slack_auth_refresh_returns_new_access_token(
    client: TestClient,
    factory,
    override_api_service,
) -> None:
    """✅ 정상 refresh 토큰 + 유저 존재 → 새 access_token 발급."""
    # given
    user = factory.make_user(user_id="U_REFRESH", name="리프레시")
    service = MagicMock()
    service.get_user_by.return_value = user
    override_api_service(service)

    refresh_token = encode_token(
        payload={"user_id": "U_REFRESH", "type": "refresh"},
        expires_delta=timedelta(days=7),
    )

    # when
    response = client.get(
        "/v1/slack/auth/refresh", params={"refresh_token": refresh_token}
    )

    # then
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    from app.api.auth import decode_token

    decoded = decode_token(body["access_token"])
    assert decoded["user_id"] == "U_REFRESH"
    assert decoded.get("type") != "refresh"
    service.get_user_by.assert_called_once_with(user_id="U_REFRESH")


def test_slack_auth_refresh_with_access_typed_token_returns_403(
    client: TestClient, override_api_service
) -> None:
    """⚠️ access 타입 토큰을 refresh 로 사용 → 403."""
    # given
    service = MagicMock()
    override_api_service(service)
    access_token = encode_token(
        payload={"user_id": "U_REFRESH"},
        expires_delta=timedelta(days=1),
    )

    # when
    response = client.get(
        "/v1/slack/auth/refresh", params={"refresh_token": access_token}
    )

    # then
    assert response.status_code == 403
    assert "토큰이 유효하지 않습니다" in response.json()["detail"]
    # 분기에서 일찍 끊겨 service 는 호출되지 않는다.
    service.get_user_by.assert_not_called()


def test_slack_auth_refresh_when_user_not_found_returns_404(
    client: TestClient, override_api_service
) -> None:
    """⚠️ 토큰은 정상이지만 유저가 없으면 → 404."""
    # given
    service = MagicMock()
    service.get_user_by.return_value = None
    override_api_service(service)
    refresh_token = encode_token(
        payload={"user_id": "U_GHOST", "type": "refresh"},
        expires_delta=timedelta(days=7),
    )

    # when
    response = client.get(
        "/v1/slack/auth/refresh", params={"refresh_token": refresh_token}
    )

    # then
    assert response.status_code == 404
    assert "해당하는 유저가 없습니다" in response.json()["detail"]
    service.get_user_by.assert_called_once_with(user_id="U_GHOST")


def test_slack_auth_refresh_with_invalid_token_returns_403(
    client: TestClient,
) -> None:
    """⚠️ JWT 디코딩 실패 → 403."""
    # when
    response = client.get(
        "/v1/slack/auth/refresh", params={"refresh_token": "not.a.real.jwt"}
    )

    # then
    assert response.status_code == 403
    assert "토큰이 유효하지 않습니다" in response.json()["detail"]


def test_slack_auth_refresh_with_expired_token_returns_403(
    client: TestClient,
) -> None:
    """🌀 만료된 refresh 토큰 → 403."""
    # given
    expired = encode_token(
        payload={"user_id": "U_X", "type": "refresh"},
        expires_delta=timedelta(seconds=-1),
    )

    # when
    response = client.get(
        "/v1/slack/auth/refresh", params={"refresh_token": expired}
    )

    # then
    assert response.status_code == 403
    assert "토큰이 유효하지 않습니다" in response.json()["detail"]


# ---------------------------------------------------------------------------
# GET /v1/slack/me
# ---------------------------------------------------------------------------


def test_slack_me_returns_current_user(client: TestClient, auth_for, factory) -> None:
    """✅ 인증된 유저 → SimpleUser JSON 응답."""
    # given
    user = factory.make_user(user_id="U_ME", name="나야나")
    auth_for(user)

    # when
    response = client.get("/v1/slack/me")

    # then
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "U_ME"
    assert body["name"] == "나야나"
    assert body["channel_name"] == user.channel_name


def test_slack_me_without_token_returns_403(client: TestClient) -> None:
    """⚠️ 인증 누락 → 403."""
    # when
    response = client.get("/v1/slack/me")

    # then
    assert response.status_code == 403
