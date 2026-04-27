"""API 라우터 테스트 공통 픽스처.

- `client`         : FastAPI TestClient. 라이프스팬 이벤트는 발화시키지 않는다.
- `auth_for(user)` : 의존성 오버라이드로 `current_user`를 주어진 user로 고정.
- `make_access_token(user_id)` : 진짜 JWT 발급 (헤더에 실어 보낼 때 사용)
"""

from __future__ import annotations

from datetime import timedelta
from typing import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from app import app as fastapi_app
from app.api import auth as auth_module
from app.api.auth import current_user, encode_token
from app.api.deps import api_repo as api_repo_dep
from app.api.deps import api_service as api_service_dep
from app.api.deps import point_service as point_service_dep
from app.models import SimpleUser, User


@pytest.fixture
def client() -> Iterator[TestClient]:
    """TestClient.

    `with TestClient(...)` 컨텍스트로 쓰지 않으므로 startup/shutdown 이벤트가 발화되지 않는다.
    덕분에 슬랙 소켓모드 핸들러가 connect_async()를 시도하지 않는다.
    """
    test_client = TestClient(fastapi_app)
    try:
        yield test_client
    finally:
        # 다음 테스트로 의존성 오버라이드가 새지 않도록 정리
        fastapi_app.dependency_overrides.clear()


@pytest.fixture
def make_access_token() -> Callable[..., str]:
    """access_token을 발급하는 헬퍼."""

    def _make(user_id: str = "U_TEST", **extra) -> str:
        payload = {"user_id": user_id, **extra}
        return encode_token(payload=payload, expires_delta=timedelta(days=1))

    return _make


@pytest.fixture
def make_refresh_token() -> Callable[..., str]:
    def _make(user_id: str = "U_TEST") -> str:
        payload = {"user_id": user_id, "type": "refresh"}
        return encode_token(payload=payload, expires_delta=timedelta(days=7))

    return _make


@pytest.fixture
def auth_for() -> Callable[[User | SimpleUser], None]:
    """주어진 user로 current_user 의존성을 오버라이드한다.

    사용법:
        auth_for(user)  # 이후 client.get(...)에 헤더 없이 호출해도 user가 주입됨
    """

    def _override(user: User | SimpleUser) -> None:
        if isinstance(user, User):
            simple = SimpleUser.model_validate(user.model_dump())
        else:
            simple = user

        async def _current_user() -> SimpleUser:
            return simple

        fastapi_app.dependency_overrides[current_user] = _current_user

    return _override


@pytest.fixture
def override_api_repo() -> Callable[[object], None]:
    """ApiRepository 의존성을 임의 객체로 교체한다."""

    def _override(repo: object) -> None:
        fastapi_app.dependency_overrides[api_repo_dep] = lambda: repo

    return _override


@pytest.fixture
def override_api_service() -> Callable[[object], None]:
    """ApiService 의존성을 임의 객체로 교체한다."""

    def _override(service: object) -> None:
        fastapi_app.dependency_overrides[api_service_dep] = lambda: service

    return _override


@pytest.fixture
def override_point_service() -> Callable[[object], None]:
    """PointService 의존성을 임의 객체로 교체한다."""

    def _override(service: object) -> None:
        fastapi_app.dependency_overrides[point_service_dep] = lambda: service

    return _override


@pytest.fixture
def auth_module_ref():
    """auth 모듈 참조를 그대로 노출 (mocker.patch 시 경로 단축용)."""
    return auth_module
