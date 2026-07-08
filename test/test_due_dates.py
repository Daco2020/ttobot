"""마감일(DUE_DATES) 자동 확장 로직 테스트.

기획: 마지막으로 하드코딩된 마감일(BASE_DUE_DATES[-1]) 이후로도
2주(14일) 간격으로 추가 회차가 무한히 자동 생성되어야 한다.
따라서 마감일 리스트를 손으로 추가할 필요가 없다.

가설 3종(성공/실패/엣지) + 2층(단위/결합)으로 구성한다.
- 단위: get_due_dates() 순수 함수 입출력
- 결합: User.get_due_date / User.get_submit_status / Content.get_round 라운드트립
"""

from __future__ import annotations

import datetime

from app.constants import BASE_DUE_DATES, get_due_dates
from test import factories


TWO_WEEKS = datetime.timedelta(days=14)


# ---------------------------------------------------------------------------
# 단위: get_due_dates() 순수 함수
# ---------------------------------------------------------------------------


def test_reference_within_base_returns_base_unchanged() -> None:
    """성공: 기준일이 기존 마감일 범위 안이면 BASE 를 그대로 돌려준다(확장 없음)."""
    reference = BASE_DUE_DATES[len(BASE_DUE_DATES) // 2]
    result = get_due_dates(reference)
    assert result == BASE_DUE_DATES


def test_reference_equal_to_last_base_does_not_extend() -> None:
    """엣지(경계): 기준일이 마지막 마감일과 정확히 같으면 확장하지 않는다."""
    result = get_due_dates(BASE_DUE_DATES[-1])
    assert result == BASE_DUE_DATES


def test_reference_past_last_base_extends_by_two_weeks() -> None:
    """성공: 기준일이 마지막 마감일을 지나면 14일 간격으로 확장한다."""
    last = BASE_DUE_DATES[-1]
    reference = last + datetime.timedelta(days=3)  # 마지막 마감일 3일 후
    result = get_due_dates(reference)

    # 원본은 보존되고, 그 뒤로 딱 한 회차(+14일)가 추가되어 기준일을 덮는다.
    assert result[: len(BASE_DUE_DATES)] == BASE_DUE_DATES
    assert result[len(BASE_DUE_DATES)] == last + TWO_WEEKS
    assert result[-1] >= reference


def test_infinite_extension_far_future() -> None:
    """엣지(무한 확장): 아주 먼 미래 기준일도 14일 간격으로 끝까지 확장된다."""
    reference = BASE_DUE_DATES[-1] + datetime.timedelta(weeks=200)
    result = get_due_dates(reference)

    assert result[-1] >= reference
    # 확장 구간은 모두 정확히 14일 간격이며 오름차순이다.
    for prev, cur in zip(
        result[len(BASE_DUE_DATES) - 1 :], result[len(BASE_DUE_DATES) :]
    ):
        assert cur - prev == TWO_WEEKS


def test_reference_before_start_returns_base_unchanged() -> None:
    """엣지: 기준일이 시작일(0회차) 이전이어도 잘라내지 않고 BASE 를 돌려준다."""
    reference = BASE_DUE_DATES[0] - datetime.timedelta(days=100)
    result = get_due_dates(reference)
    assert result == BASE_DUE_DATES


def test_historical_irregular_gap_is_preserved() -> None:
    """실패 방지: 비상계엄 연장(28일 간격)이라는 역사적 예외가 확장 로직에 뭉개지지 않는다."""
    result = get_due_dates(BASE_DUE_DATES[-1] + datetime.timedelta(weeks=10))
    gaps = {(cur - prev).days for prev, cur in zip(result, result[1:])}
    # 역사 구간에는 28일 예외가 존재해야 한다.
    assert 28 in gaps


def test_result_is_strictly_ascending() -> None:
    """엣지(정합성): 반환 리스트는 항상 순증가한다."""
    result = get_due_dates(BASE_DUE_DATES[-1] + datetime.timedelta(weeks=50))
    for prev, cur in zip(result, result[1:]):
        assert prev < cur


def test_pure_function_does_not_mutate_base() -> None:
    """엣지(멱등/부작용): 여러 번 호출해도 BASE_DUE_DATES 원본은 변하지 않는다."""
    before = list(BASE_DUE_DATES)
    get_due_dates(BASE_DUE_DATES[-1] + datetime.timedelta(weeks=30))
    get_due_dates(BASE_DUE_DATES[-1] + datetime.timedelta(weeks=30))
    assert BASE_DUE_DATES == before


# ---------------------------------------------------------------------------
# 결합: 모델 메서드 round-trip
# ---------------------------------------------------------------------------


def test_get_due_date_no_longer_raises_after_season_end(mocker) -> None:
    """결합(핵심): 마지막 하드코딩 마감일을 지난 시점에도 예외 없이 다음 회차를 반환한다.

    기존에는 BotException('지금은 글또 글 제출 기간이 아니에요.') 가 났지만
    이제는 자동 생성된 회차를 돌려주어야 한다.
    """
    after_last = BASE_DUE_DATES[-1] + datetime.timedelta(days=3)
    mocker.patch(
        "app.models.tz_now",
        return_value=datetime.datetime(
            after_last.year, after_last.month, after_last.day, 12, 0, 0
        ),
    )
    user = factories.make_user(contents=[])

    round_, due_date = user.get_due_date()

    assert due_date == BASE_DUE_DATES[-1] + TWO_WEEKS
    assert round_ == len(BASE_DUE_DATES)  # 0-indexed → 새로 생성된 회차 번호


def test_content_get_round_for_auto_generated_round() -> None:
    """결합: 자동 생성된 미래 회차에 제출된 콘텐츠의 회차 번호도 올바르게 계산된다."""
    # 마지막 마감일 + 1주(직전 마감일 초과, 새 마감일 이하) 시점에 제출
    submit_date = BASE_DUE_DATES[-1] + datetime.timedelta(days=7)
    content = factories.make_content(dt=f"{submit_date} 12:00:00")

    assert content.get_round() == len(BASE_DUE_DATES)


def test_get_submit_status_spans_generated_boundary(mocker) -> None:
    """결합: 현재 시점이 자동 생성 구간이어도 회차별 제출 현황이 끊기지 않고 계산된다."""
    now = BASE_DUE_DATES[-1] + datetime.timedelta(days=20)  # 새 회차 하나를 넘긴 시점
    mocker.patch(
        "app.models.tz_now",
        return_value=datetime.datetime(now.year, now.month, now.day, 12, 0, 0),
    )
    # 마지막 하드코딩 마감일 직후(=새 46회차 구간)에 제출한 콘텐츠
    submit_date = BASE_DUE_DATES[-1] + datetime.timedelta(days=7)
    content = factories.make_content(dt=f"{submit_date} 12:00:00", type="submit")
    user = factories.make_user(contents=[content])

    status = user.get_submit_status()

    # 새로 생성된 회차(len(BASE_DUE_DATES))가 '제출'로 잡혀야 한다.
    assert status.get(len(BASE_DUE_DATES)) == "제출"
