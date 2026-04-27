"""API 테스트 인프라 스모크 테스트.

라우터를 본격적으로 검증하기 전, TestClient가 살아있는지/의존성 오버라이드가 동작하는지 확인.
"""

from fastapi.testclient import TestClient


def test_health_endpoint_returns_true(client: TestClient) -> None:
    # given: client 픽스처

    # when
    response = client.get("/")

    # then
    assert response.status_code == 200
    assert response.json() is True


def test_protected_endpoint_without_token_returns_403(client: TestClient) -> None:
    """current_user 의존성이 토큰 부재 시 403을 반환하는지 (스모크)."""
    # when
    response = client.get("/v1/slack/me")

    # then
    assert response.status_code == 403


def test_auth_for_overrides_current_user(client: TestClient, auth_for, factory) -> None:
    """auth_for 픽스처로 current_user를 오버라이드 하면 인증을 통과한다."""
    # given
    user = factory.make_user(user_id="U_OVERRIDE", name="오버라이드유저")
    auth_for(user)

    # when
    response = client.get("/v1/slack/me")

    # then
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "U_OVERRIDE"
    assert body["name"] == "오버라이드유저"
