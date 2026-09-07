"""self-ping(keepalive) 테스트.

기획: Koyeb 무료 인스턴스는 1시간 인바운드 트래픽이 없으면 scale-to-zero 되고, 슬랙 소켓은
아웃바운드라 트래픽으로 세지 않는다. 자기 공개 URL(KOYEB_URL)을 5분마다 GET 해서 인바운드
트래픽을 만든다 (sigongbot-mini 에서 검증된 패턴). 어떤 경우에도 예외를 내지 않는다.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx

from app.keepalive import ping_self


def _mock_client(mocker, *, status: int = 200, exc: Exception | None = None):
    client = AsyncMock()
    if exc is not None:
        client.get = AsyncMock(side_effect=exc)
    else:
        client.get = AsyncMock(return_value=SimpleNamespace(status_code=status))
    async_client = mocker.patch("app.keepalive.httpx.AsyncClient")
    async_client.return_value.__aenter__.return_value = client
    return client, async_client


async def test_ping_returns_true_and_hits_url(mocker) -> None:
    """✅ 200 → True, 정확히 그 URL 로 1회 GET."""
    client, _ = _mock_client(mocker, status=200)

    assert await ping_self("https://ttobot.koyeb.app") is True
    client.get.assert_awaited_once_with("https://ttobot.koyeb.app")


async def test_ping_non_2xx_still_counts_as_traffic(mocker) -> None:
    """🌀 503 이어도 엣지에 인바운드 요청이 도달한 것이므로 True."""
    _mock_client(mocker, status=503)

    assert await ping_self("https://x") is True


async def test_ping_swallows_network_error(mocker) -> None:
    """⚠️ 타임아웃/연결 실패는 False 로 삼키고 예외를 내지 않는다 (스케줄러를 죽이면 안 됨)."""
    _mock_client(mocker, exc=httpx.ConnectTimeout("timeout"))

    assert await ping_self("https://x") is False


async def test_ping_disabled_when_url_empty(mocker) -> None:
    """🌀 URL 이 비어 있으면 요청 없이 False (KOYEB_URL 미설정 = 비활성)."""
    _, async_client = _mock_client(mocker)

    assert await ping_self("   ") is False
    async_client.assert_not_called()
