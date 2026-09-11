"""PointService.get_user_point: 미들웨어가 넣어 준 user 를 그대로 받는다 (worklog 023).

user_id 로 받으면 users·contents CSV 를 한 번 더 읽었다. 0.1 vCPU 에서 포인트 내역 보기가
3초(trigger 만료)를 넘기던 원인 중 하나.
"""

from __future__ import annotations

from pytest_mock import MockerFixture

from app.models import PointHistory
from app.slack.repositories import SlackRepository
from app.slack.services.point import PointService
from test import factories


def _history_row(**overrides: str) -> dict[str, str]:
    row = {
        "id": "h1",
        "user_id": "U1",
        "reason": "글 제출",
        "point": "100",
        "category": "글쓰기",
        "created_at": "2026-09-01 10:00:00",
    }
    row.update(overrides)
    return row


def test_get_user_point_uses_given_user_without_reloading(
    mocker: MockerFixture,
) -> None:
    """✅ 받은 user 를 그대로 쓰고 저장소에서 유저를 다시 읽지 않는다."""
    user = factories.make_user(user_id="U1")
    repo = mocker.MagicMock(spec=SlackRepository)
    repo.fetch_point_histories.return_value = [
        factories.make_point_history(user_id="U1", point=100)
    ]

    result = PointService(repo=repo).get_user_point(user=user)

    repo.get_user.assert_not_called()
    repo.fetch_point_histories.assert_called_once_with("U1")
    assert result.user.user_id == "U1"
    assert result.total_point == 100


def test_get_user_point_reads_only_that_users_histories(
    tmp_store, csv_writer_helper
) -> None:
    """결합: CSV 에서 그 사용자의 내역만 최신순으로 가져온다."""
    csv_writer_helper(
        tmp_store / "point_histories.csv",
        PointHistory.fieldnames(),
        [
            _history_row(id="a", created_at="2026-09-01 10:00:00"),
            _history_row(id="b", user_id="U2", created_at="2026-09-02 10:00:00"),
            _history_row(id="c", point="50", created_at="2026-09-03 10:00:00"),
        ],
    )

    result = PointService(repo=SlackRepository()).get_user_point(
        user=factories.make_user(user_id="U1")
    )

    assert [h.id for h in result.point_histories] == ["c", "a"]
    assert result.total_point == 150


def test_get_user_point_without_histories_is_empty(tmp_store) -> None:
    """🌀 내역이 없으면 빈 목록, 0점."""
    result = PointService(repo=SlackRepository()).get_user_point(
        user=factories.make_user(user_id="U1")
    )

    assert result.point_histories == []
    assert result.total_point == 0
