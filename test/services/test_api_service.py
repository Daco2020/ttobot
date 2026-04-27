"""ApiService (app/api/services.py) 단위 테스트.

대상:
- send_paper_plane
- fetch_current_week_paper_planes (시간 경계 검증 위주)
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from pytest_mock import MockerFixture

from app.api.services import ApiService
from app.models import PaperPlane
from test import factories


# ---------------------------------------------------------------------------
# send_paper_plane
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_paper_plane_creates_plane_and_sends_two_messages(
    mocker: MockerFixture,
) -> None:
    """✅ receiver 존재 → PaperPlane 생성 + repo create + 큐 적재 + chat_postMessage 두 번."""
    # given
    receiver = factories.make_user(user_id="U_RECEIVER", name="수신자")
    repo = MagicMock()
    repo.get_user.return_value = receiver
    repo.create_paper_plane.return_value = None
    upload_queue = mocker.patch("app.api.services.store.paper_plane_upload_queue", new=[])
    slack_client = AsyncMock()

    service = ApiService(api_repo=repo)

    # when
    result = await service.send_paper_plane(
        sender_id="U_SENDER",
        sender_name="발신자",
        receiver_id="U_RECEIVER",
        text="감사합니다.",
        client=slack_client,
    )

    # then
    assert isinstance(result, PaperPlane)
    assert result.sender_id == "U_SENDER"
    assert result.sender_name == "발신자"
    assert result.receiver_id == "U_RECEIVER"
    assert result.receiver_name == "수신자"
    assert result.text == "감사합니다."
    repo.create_paper_plane.assert_called_once()
    assert len(upload_queue) == 1
    # 슬랙 메시지는 채널과 발신자 DM 두 번 전송된다.
    assert slack_client.chat_postMessage.await_count == 2


@pytest.mark.asyncio
async def test_send_paper_plane_when_receiver_not_found_raises_404(
    mocker: MockerFixture,
) -> None:
    """⚠️ receiver 못 찾으면 HTTPException(404)."""
    # given
    repo = MagicMock()
    repo.get_user.return_value = None
    slack_client = AsyncMock()
    service = ApiService(api_repo=repo)

    # when / then
    with pytest.raises(HTTPException) as exc_info:
        await service.send_paper_plane(
            sender_id="U_SENDER",
            sender_name="발신자",
            receiver_id="U_GHOST",
            text="hi",
            client=slack_client,
        )
    assert exc_info.value.status_code == 404
    assert "받는 사람을 찾을 수 없어요" in exc_info.value.detail
    repo.create_paper_plane.assert_not_called()
    slack_client.chat_postMessage.assert_not_awaited()


# ---------------------------------------------------------------------------
# fetch_current_week_paper_planes
# ---------------------------------------------------------------------------
#
# 토요일 00:00 ~ 금요일 23:59:59 가 한 주.
# 테스트 기준일: 2025-01-15 (수요일, weekday=2).
#  - last_saturday = today - 4days = 2025-01-11 (Sat)
#  - start_dt = 2025-01-11 00:00:00
#  - end_dt   = 2025-01-17 23:59:59.999999 (Fri)


def _plane_at(created_at: str) -> PaperPlane:
    return factories.make_paper_plane(
        sender_id="U_SENDER", created_at=created_at
    )


def _fixed_today() -> datetime.datetime:
    return datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))


@pytest.fixture
def fix_today(mocker: MockerFixture):
    return mocker.patch("app.api.services.tz_now", return_value=_fixed_today())


def test_fetch_current_week_paper_planes_filters_within_week(fix_today) -> None:
    """✅ 이번 주 토~금 범위 내의 비행기만 반환."""
    repo = MagicMock()
    repo.fetch_paper_planes.return_value = [
        _plane_at("2025-01-13 09:00:00"),  # 월요일 - IN
        _plane_at("2025-01-08 09:00:00"),  # 지난주 수요일 - OUT
        _plane_at("2025-01-20 09:00:00"),  # 다음주 월요일 - OUT
    ]
    service = ApiService(api_repo=repo)

    result = service.fetch_current_week_paper_planes(user_id="U_SENDER")

    assert len(result) == 1
    assert result[0].created_at == "2025-01-13 09:00:00"


def test_fetch_current_week_paper_planes_includes_saturday_start_boundary(fix_today) -> None:
    """🌀 토요일 00:00 정시 → 포함."""
    repo = MagicMock()
    repo.fetch_paper_planes.return_value = [
        _plane_at("2025-01-11 00:00:00"),  # 정확히 시작 boundary
    ]
    service = ApiService(api_repo=repo)

    result = service.fetch_current_week_paper_planes(user_id="U_SENDER")

    assert len(result) == 1


def test_fetch_current_week_paper_planes_excludes_just_before_start(fix_today) -> None:
    """🌀 시작 전 1초 → 제외."""
    repo = MagicMock()
    repo.fetch_paper_planes.return_value = [
        _plane_at("2025-01-10 23:59:59"),  # 금요일 23:59:59 (지난주)
    ]
    service = ApiService(api_repo=repo)

    result = service.fetch_current_week_paper_planes(user_id="U_SENDER")

    assert result == []


def test_fetch_current_week_paper_planes_includes_friday_end_boundary(fix_today) -> None:
    """🌀 금요일 23:59:59 → 포함 (end_dt 는 .999999 까지여서 포함)."""
    repo = MagicMock()
    repo.fetch_paper_planes.return_value = [
        _plane_at("2025-01-17 23:59:59"),
    ]
    service = ApiService(api_repo=repo)

    result = service.fetch_current_week_paper_planes(user_id="U_SENDER")

    assert len(result) == 1


def test_fetch_current_week_paper_planes_excludes_after_friday(fix_today) -> None:
    """🌀 토요일 00:00 → 제외 (다음 주의 시작)."""
    repo = MagicMock()
    repo.fetch_paper_planes.return_value = [
        _plane_at("2025-01-18 00:00:00"),
    ]
    service = ApiService(api_repo=repo)

    result = service.fetch_current_week_paper_planes(user_id="U_SENDER")

    assert result == []


def test_fetch_current_week_paper_planes_returns_empty_when_no_planes(
    fix_today,
) -> None:
    """🌀 비행기 자체가 없을 때 빈 리스트."""
    repo = MagicMock()
    repo.fetch_paper_planes.return_value = []
    service = ApiService(api_repo=repo)

    result = service.fetch_current_week_paper_planes(user_id="U_SENDER")

    assert result == []
