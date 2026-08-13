"""SlackService.get_title 단위 테스트.

기획: Medium 처럼 Cloudflare 봇 차단(403)을 거는 사이트는 서버가 글을 읽을 수 없다.
사람이 브라우저로 열면 정상인 글이므로 URL 자체는 통과시키고, 제목만 직접 입력받는다.
반면 진짜 403(권한 없음)과 404(없는 글)는 지금처럼 막는다.

봇 차단 판별 근거: Cloudflare 챌린지 응답에만 `cf-mitigated` 헤더가 붙는다.
(실측: Medium 403 -> cf-mitigated=challenge / httpbin 일반 403 -> 헤더 없음)

가설 3종(성공/실패/엣지)으로 구성한다.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.exception import ClientException
from app.slack.services.base import SlackService


def _mock_response(
    mocker, *, status: int, headers: dict | None = None, body: bytes = b""
):
    """httpx.AsyncClient 를 mock 해서 지정한 응답을 돌려준다."""
    response = SimpleNamespace(
        status_code=status,
        headers=httpx.Headers(headers or {}),
        content=body,
    )
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    async_client = mocker.patch("app.slack.services.base.httpx.AsyncClient")
    async_client.return_value.__aenter__.return_value = client
    return client


def _view(manual_title: str | None = None) -> dict:
    """제출 모달의 state 중 이 함수가 읽는 부분만 최소로 구성."""
    return {
        "state": {
            "values": {
                "manual_title_input": {"title_input": {"value": manual_title}},
            }
        }
    }


@pytest.fixture
def service() -> SlackService:
    return SlackService(repo=MagicMock(), user=MagicMock())


# 실제 Cloudflare 챌린지 응답의 특징 (실측값)
CF_CHALLENGE_HEADERS = {"cf-mitigated": "challenge", "server": "cloudflare"}
CF_CHALLENGE_BODY = (
    b"<html><head><title>Just a moment...</title></head><body></body></html>"
)


# ---------------------------------------------------------------------------
# 성공
# ---------------------------------------------------------------------------


async def test_normal_page_returns_title(service, mocker) -> None:
    """✅ 정상 200 + <title> → 제목을 반환한다."""
    _mock_response(
        mocker,
        status=200,
        body="<html><head><title>  테스트 글  </title></head></html>".encode(),
    )

    title = await service.get_title(_view(), "https://example.com/post")

    assert title == "테스트 글"


async def test_bot_blocked_with_manual_title_passes(service, mocker) -> None:
    """✅ 봇 차단(403 + cf-mitigated) + 제목 직접 입력 → URL 을 통과시키고 그 제목을 쓴다.

    이번 수정의 핵심. 기존에는 403 이라는 이유로 제출 자체가 막혔다.
    """
    _mock_response(
        mocker,
        status=403,
        headers=CF_CHALLENGE_HEADERS,
        body=CF_CHALLENGE_BODY,
    )

    title = await service.get_title(
        _view("아내가 바이브 코딩을 시작했다 (3편)"),
        "https://medium.com/@Jager-yoo/wife-vibe-coding-3",
    )

    assert title == "아내가 바이브 코딩을 시작했다 (3편)"


async def test_manual_title_takes_precedence(service, mocker) -> None:
    """✅ 정상 응답이어도 직접 입력한 제목이 우선한다 (기존 동작 보존)."""
    _mock_response(
        mocker, status=200, body=b"<html><head><title>page</title></head></html>"
    )

    title = await service.get_title(_view("내가 정한 제목"), "https://example.com/post")

    assert title == "내가 정한 제목"


# ---------------------------------------------------------------------------
# 실패
# ---------------------------------------------------------------------------


async def test_bot_blocked_without_manual_title_asks_for_input(service, mocker) -> None:
    """⚠️ 봇 차단인데 제목 미입력 → 직접 입력하라고 안내한다."""
    _mock_response(
        mocker, status=403, headers=CF_CHALLENGE_HEADERS, body=CF_CHALLENGE_BODY
    )

    with pytest.raises(ClientException) as e:
        await service.get_title(_view(), "https://medium.com/@x/y")

    assert "직접 입력" in str(e.value)


async def test_genuine_403_is_still_blocked(service, mocker) -> None:
    """⚠️ cf-mitigated 없는 진짜 403 → 제목을 입력했어도 막는다 (검증 정책 유지)."""
    _mock_response(mocker, status=403, headers={"server": "gunicorn/19.9.0"}, body=b"")

    with pytest.raises(ClientException) as e:
        await service.get_title(_view("제목을 넣어도"), "https://example.com/forbidden")

    assert "403" in str(e.value)


async def test_404_is_blocked(service, mocker) -> None:
    """⚠️ 404 → 비공개/없는 글로 막는다."""
    _mock_response(mocker, status=404)

    with pytest.raises(ClientException) as e:
        await service.get_title(_view("제목"), "https://example.com/missing")

    assert "404" in str(e.value)


# ---------------------------------------------------------------------------
# 엣지
# ---------------------------------------------------------------------------


async def test_no_title_tag_without_manual_title_raises(service, mocker) -> None:
    """🌀 200 인데 <title> 이 없고 직접 입력도 없음 → 직접 입력 안내 (기존 동작)."""
    _mock_response(mocker, status=200, body=b"<html><body>no title</body></html>")

    with pytest.raises(ClientException) as e:
        await service.get_title(_view(), "https://example.com/notitle")

    assert "직접 입력" in str(e.value)


async def test_no_title_tag_with_manual_title_passes(service, mocker) -> None:
    """🌀 200 인데 <title> 이 없어도 직접 입력했으면 통과한다."""
    _mock_response(mocker, status=200, body=b"<html><body>no title</body></html>")

    title = await service.get_title(
        _view("직접 쓴 제목"), "https://example.com/notitle"
    )

    assert title == "직접 쓴 제목"


async def test_bot_block_signal_requires_403(service, mocker) -> None:
    """🌀 200 인데 cf-mitigated 헤더가 있는 경우는 봇 차단이 아니다 (정상 파싱)."""
    _mock_response(
        mocker,
        status=200,
        headers={"cf-mitigated": "challenge"},
        body="<html><head><title>정상</title></head></html>".encode(),
    )

    assert await service.get_title(_view(), "https://example.com/ok") == "정상"
