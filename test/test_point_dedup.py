"""공지 확인 / 성윤을 잡아라 포인트 중복 판정을 point_histories 로 (worklog 021).

로컬 전용 _checked_*.csv 는 Koyeb 재배포마다 사라져 중복 지급 창이 열렸다. 동기화·복원되는
point_histories 의 id 를 결정적으로(notice:{user}:{ts}) 만들어 그 존재로 판정한다.
PointHistory.id 를 키로 쓰는 코드는 없어 스키마·표시 문구 변경이 없다.
"""

from __future__ import annotations

import pytest

from app import store as store_module
from app.slack.repositories import SlackRepository
from app.slack.services.point import (
    PointService,
    notice_history_id,
    super_admin_post_history_id,
)
from test import factories


@pytest.fixture(autouse=True)
def _reset_queue():
    store_module.point_history_upload_queue = []
    yield
    store_module.point_history_upload_queue = []


def test_ids_are_deterministic_and_distinct() -> None:
    """✅ 같은 입력이면 같은 id, 종류·사용자·ts 가 다르면 다른 id."""
    assert notice_history_id("U1", "1.0") == notice_history_id("U1", "1.0")
    assert notice_history_id("U1", "1.0") != notice_history_id("U2", "1.0")
    assert notice_history_id("U1", "1.0") != notice_history_id("U1", "2.0")
    assert notice_history_id("U1", "1.0") != super_admin_post_history_id("U1", "1.0")


def test_has_point_history_id_false_when_empty(tmp_store) -> None:
    """🌀 내역이 없으면 False."""
    assert (
        SlackRepository().has_point_history_id(notice_history_id("U1", "1.0")) is False
    )


def test_grant_notice_writes_deterministic_id_then_detectable(tmp_store) -> None:
    """결합: 지급 → CSV 에 결정적 id 로 기록 → 같은 공지 재확인은 판정됨 → 다른 공지는 아님."""
    repo = SlackRepository()
    service = PointService(repo=repo)

    service.grant_if_notice_emoji_checked(user_id="U1", notice_ts="1.0")

    assert repo.has_point_history_id(notice_history_id("U1", "1.0")) is True
    assert repo.has_point_history_id(notice_history_id("U1", "2.0")) is False
    assert repo.has_point_history_id(notice_history_id("U2", "1.0")) is False
    # 시트 업로드 큐에도 같은 id 가 실린다 (복원 시 판정이 유지되도록)
    assert store_module.point_history_upload_queue[0][0] == notice_history_id(
        "U1", "1.0"
    )


def test_grant_super_admin_post_uses_its_own_id(tmp_store) -> None:
    """✅ 성윤을 잡아라도 같은 방식, 별도 네임스페이스."""
    repo = SlackRepository()
    PointService(repo=repo).grant_if_super_admin_post_reacted(
        user_id="U1", post_ts="9.0"
    )

    assert repo.has_point_history_id(super_admin_post_history_id("U1", "9.0")) is True
    assert repo.has_point_history_id(notice_history_id("U1", "9.0")) is False


def test_legacy_random_id_history_does_not_block(tmp_store) -> None:
    """⚠️ 옛 내역(무작위 id, 사유 '공지사항 확인')은 판정에 안 잡힌다. 컷오버 후 3일 창에서
    1회 중복 지급이 가능한 것을 문서화하는 테스트."""
    repo = SlackRepository()
    repo.add_point(factories.make_point_history(user_id="U1", reason="공지사항 확인"))

    assert repo.has_point_history_id(notice_history_id("U1", "1.0")) is False


def test_reason_and_point_unchanged(tmp_store) -> None:
    """✅ 사용자에게 보이는 사유·점수는 그대로 (표시 문구 변경 없음)."""
    repo = SlackRepository()
    PointService(repo=repo).grant_if_notice_emoji_checked(user_id="U1", notice_ts="1.0")

    history = repo.fetch_point_histories("U1")[0]
    assert history.reason == "공지사항 확인"
    assert history.point == 20
