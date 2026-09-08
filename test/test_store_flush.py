"""upload_queue 리팩터링 테스트 (worklog 020).

한도(공식): 사용자당 읽기·쓰기 각 60/분, 배치 요청은 1건. 틱은 20초(분당 3회).
- 갱신 3테이블은 틱당 배치읽기 1 + 배치쓰기 1
- 키를 못 찾으면 어떤 행도 쓰지 않는다 (기존: row_number 초기값 2로 첫 데이터 행을 덮어씀)
- 429 → 틱 단위 지수 백오프 1·2·4분, 최대 5분. force 면 무시 (shutdown 마지막 flush 용)
- 큐 정리는 인덱스 슬라이스 (업로드 중 append 된 동일값 유실 방지)
- writing_participation 은 replace_table 1회
- 틱당 요청 예산 초과분은 이월, 큐는 성공 전엔 지우지 않는다
실패 / 성공 / 엣지 × 단위 / 결합.
"""

from __future__ import annotations

import csv
from unittest.mock import MagicMock

import pytest
from gspread.exceptions import APIError

from app import store as store_module
from app.store import (
    MAX_REQUESTS_PER_TICK,
    FlushReport,
    SheetQuotaExceeded,
    Store,
    flush_alerts,
    merge_writing_participation,
    next_prev_deferred,
)
from test import factories

WP = "writing_participation"


def _api_error(status: int) -> APIError:
    response = MagicMock()
    response.status_code = status
    response.json.return_value = {
        "error": {"code": status, "message": "x", "status": "ERR"}
    }
    response.text = "x"
    return APIError(response)


@pytest.fixture(autouse=True)
def _reset_state():
    names = [
        n
        for n in dir(store_module)
        if n.endswith("_queue") and isinstance(getattr(store_module, n), list)
    ]

    def reset() -> None:
        for n in names:
            setattr(store_module, n, [])
        store_module.writing_participation_dirty = False
        store_module._backoff_until = 0.0
        store_module._backoff_level = 0

    reset()
    yield
    reset()


@pytest.fixture
def client() -> MagicMock:
    c = MagicMock()
    c.batch_get.return_value = []
    c.get_values.return_value = []  # WP 병합이 읽는 시트 탭, 기본 빈 탭
    return c


@pytest.fixture
def store(client) -> Store:
    return Store(client=client)


class Clock:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def _bookmark(user_id: str, content_ts: str):
    return factories.make_bookmark(user_id=user_id, content_ts=content_ts)


# ---------------------------------------------------------------------------
# 백오프
# ---------------------------------------------------------------------------


async def test_429_raises_quota_error_and_keeps_queue(store, client, tmp_store):
    """⚠️ 429 → SheetQuotaExceeded(level 1, 60초). 큐는 그대로 남아 백오프 뒤 재시도."""
    store_module.content_upload_queue.append(["row"])
    client.bulk_upload.side_effect = _api_error(429)
    clock = Clock()

    with pytest.raises(SheetQuotaExceeded) as e:
        await store.upload_queue(now=clock)

    assert e.value.level == 1
    assert e.value.retry_after == 60
    assert store_module.content_upload_queue == [["row"]]


async def test_tick_inside_backoff_window_does_nothing(store, client, tmp_store):
    """✅ 백오프 창 안의 틱은 요청 0 + backed_off 보고."""
    store_module.content_upload_queue.append(["row"])
    client.bulk_upload.side_effect = _api_error(429)
    clock = Clock()
    with pytest.raises(SheetQuotaExceeded):
        await store.upload_queue(now=clock)
    client.reset_mock()

    clock.t += 30  # 60초 창 안
    report = await store.upload_queue(now=clock)

    assert report.backed_off is True
    client.bulk_upload.assert_not_called()


@pytest.mark.parametrize(
    "hits, expected", [(1, 60), (2, 120), (3, 240), (4, 300), (5, 300)]
)
async def test_backoff_escalates_then_caps(store, client, tmp_store, hits, expected):
    """⚠️ 연속 429: 1·2·4분 → 최대 5분에서 멈춘다."""
    store_module.content_upload_queue.append(["row"])
    client.bulk_upload.side_effect = _api_error(429)
    clock = Clock()
    retry_after = None
    for _ in range(hits):
        with pytest.raises(SheetQuotaExceeded) as e:
            await store.upload_queue(now=clock)
        retry_after = e.value.retry_after
        clock.t += retry_after + 1  # 창이 끝난 뒤 다시 시도

    assert retry_after == expected


async def test_backoff_resets_after_successful_tick(store, client, tmp_store):
    """✅ 창이 끝나고 성공하면 레벨이 0으로 돌아온다."""
    store_module.content_upload_queue.append(["row"])
    client.bulk_upload.side_effect = [_api_error(429), None]
    clock = Clock()
    with pytest.raises(SheetQuotaExceeded):
        await store.upload_queue(now=clock)
    clock.t += 61

    report = await store.upload_queue(now=clock)

    assert report.backed_off is False
    assert store_module._backoff_level == 0
    assert store_module.content_upload_queue == []


async def test_non_quota_api_error_propagates_without_backoff(store, client, tmp_store):
    """🌀 403 같은 다른 APIError 는 백오프 없이 그대로 올라간다 (기존 알림 경로)."""
    store_module.content_upload_queue.append(["row"])
    client.bulk_upload.side_effect = _api_error(403)

    with pytest.raises(APIError):
        await store.upload_queue(now=Clock())

    assert store_module._backoff_level == 0
    assert store_module._backoff_until == 0.0


async def test_force_bypasses_backoff_for_shutdown_flush(store, client, tmp_store):
    """🌀 shutdown 의 마지막 flush: 백오프 창 안이어도 force 면 시도한다."""
    store_module.content_upload_queue.append(["row"])
    client.bulk_upload.side_effect = [_api_error(429), None]
    clock = Clock()
    with pytest.raises(SheetQuotaExceeded):
        await store.upload_queue(now=clock)
    clock.t += 5

    report = await store.upload_queue(force=True, now=clock)

    assert report.backed_off is False
    assert store_module.content_upload_queue == []


async def test_backoff_expiry_boundary_is_inclusive(store, client, tmp_store):
    """🌀 now == until 인 순간은 창이 끝난 것으로 본다."""
    store_module.content_upload_queue.append(["row"])
    client.bulk_upload.side_effect = [_api_error(429), None]
    clock = Clock()
    with pytest.raises(SheetQuotaExceeded):
        await store.upload_queue(now=clock)
    clock.t = store_module._backoff_until

    report = await store.upload_queue(now=clock)

    assert report.backed_off is False


# ---------------------------------------------------------------------------
# 큐 정리: 인덱스 슬라이스
# ---------------------------------------------------------------------------


async def test_items_appended_during_upload_survive(store, client, tmp_store):
    """🌀 업로드 중(await 지점) append 된 항목은 다음 틱까지 남는다."""
    store_module.content_upload_queue.append(["a"])

    def append_during_upload(*_args, **_kwargs):
        store_module.content_upload_queue.append(["late"])

    client.bulk_upload.side_effect = append_during_upload

    await store.upload_queue(now=Clock())

    assert store_module.content_upload_queue == [["late"]]


async def test_identical_value_appended_during_upload_is_not_dropped(
    store, client, tmp_store
):
    """🌀 기존 initial_queue 버그: 업로드된 값과 같은 값이 도중에 들어오면 사라졌다. 이제 보존."""
    store_module.content_upload_queue.append(["same"])

    def append_same(*_args, **_kwargs):
        store_module.content_upload_queue.append(["same"])

    client.bulk_upload.side_effect = append_same

    await store.upload_queue(now=Clock())

    assert store_module.content_upload_queue == [["same"]]


async def test_upload_failure_keeps_whole_queue(store, client, tmp_store):
    """⚠️ 업로드 예외 → 큐를 하나도 지우지 않는다."""
    store_module.content_upload_queue.extend([["a"], ["b"]])
    client.bulk_upload.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await store.upload_queue(now=Clock())

    assert store_module.content_upload_queue == [["a"], ["b"]]


async def test_only_drained_items_are_committed(store, client, tmp_store):
    """✅ 업로드된 개수만큼만 앞에서 제거한다."""
    store_module.content_upload_queue.extend([["a"], ["b"]])

    await store.upload_queue(now=Clock())

    client.bulk_upload.assert_called_once_with("contents", [["a"], ["b"]])
    assert store_module.content_upload_queue == []


# ---------------------------------------------------------------------------
# 갱신: 배치읽기 1 + 배치쓰기 1
# ---------------------------------------------------------------------------


async def test_updates_across_tables_use_one_read_and_one_write(
    store, client, tmp_store
):
    """✅ bookmark 2 + subscriptions 1 + users 1 → batch_get 1회, batch_update 1회, 행 번호 정확."""
    store_module.bookmark_update_queue.extend(
        [_bookmark("U1", "1.0"), _bookmark("U2", "2.0")]
    )
    store_module.subscription_update_queue.append(
        {
            "id": "S9",
            "user_id": "U1",
            "target_user_id": "U2",
            "target_user_channel": "C",
            "status": "cancel",
            "created_at": "t",
            "updated_at": "t",
        }
    )
    store_module.user_update_queue.append(["U2", "이름", "ch", "C", "소개", "10기"])
    client.batch_get.return_value = [
        [["U0", "x", "0.0"], ["U1", "x", "1.0"], ["U2", "x", "2.0"]],  # bookmark!A2:C
        [["S8"], ["S9"]],  # subscriptions!A2:A
        [["U1"], ["U2"]],  # users!A2:A
    ]

    report = await store.upload_queue(now=Clock())

    client.batch_get.assert_called_once_with(
        ["bookmark!A2:C", "subscriptions!A2:A", "users!A2:A"]
    )
    client.batch_update.assert_called_once()
    ranges = [d["range"] for d in client.batch_update.call_args.args[0]]
    assert ranges == [
        "bookmark!A3:G3",
        "bookmark!A4:G4",
        "subscriptions!A3:G3",
        "users!A3:F3",
    ]
    assert report.skipped == []
    assert store_module.bookmark_update_queue == []
    assert store_module.subscription_update_queue == []
    assert store_module.user_update_queue == []


async def test_missing_key_writes_nothing(store, client, tmp_store):
    """⚠️ 키를 하나도 못 찾으면 batch_update 를 호출하지 않고 skipped 로 보고한다."""
    store_module.user_update_queue.append(["U_NOPE", "n", "c", "C", "i", "10기"])
    client.batch_get.return_value = [[["U1"], ["U2"]]]

    report = await store.upload_queue(now=Clock())

    client.batch_update.assert_not_called()
    assert report.skipped == ["users:U_NOPE"]
    assert store_module.user_update_queue == []  # 무한 재시도 대신 버리고 알린다


async def test_missing_key_never_touches_row_2(store, client, tmp_store):
    """⚠️ 기존 버그 회귀: 못 찾은 항목이 2행을 덮어쓰지 않는다. 찾은 것만 쓴다."""
    store_module.user_update_queue.extend(
        [["U_NOPE", "n", "c", "C", "i", "10기"], ["U2", "n", "c", "C", "i", "10기"]]
    )
    client.batch_get.return_value = [[["U1"], ["U2"]]]

    report = await store.upload_queue(now=Clock())

    data = client.batch_update.call_args.args[0]
    assert [d["range"] for d in data] == ["users!A3:F3"]
    assert all(not d["range"].endswith("A2:F2") for d in data)
    assert report.skipped == ["users:U_NOPE"]


async def test_same_row_updated_twice_last_wins(store, client, tmp_store):
    """🌀 같은 틱에 같은 행이 두 번 → 마지막 값 하나만 쓴다."""
    store_module.user_update_queue.extend(
        [["U1", "old", "c", "C", "i", "10기"], ["U1", "new", "c", "C", "i", "10기"]]
    )
    client.batch_get.return_value = [[["U1"]]]

    await store.upload_queue(now=Clock())

    data = client.batch_update.call_args.args[0]
    assert len(data) == 1
    assert data[0]["values"] == [["U1", "new", "c", "C", "i", "10기"]]


async def test_no_pending_updates_means_no_read(store, client, tmp_store):
    """🌀 갱신 큐가 비면 batch_get 도 부르지 않는다 (읽기 0)."""
    await store.upload_queue(now=Clock())

    client.batch_get.assert_not_called()
    client.batch_update.assert_not_called()


async def test_header_only_sheet_skips_everything(store, client, tmp_store):
    """🌀 시트에 데이터 행이 없으면(batch_get 빈 값) 전부 skipped."""
    store_module.user_update_queue.append(["U1", "n", "c", "C", "i", "10기"])
    client.batch_get.return_value = [[]]

    report = await store.upload_queue(now=Clock())

    client.batch_update.assert_not_called()
    assert report.skipped == ["users:U1"]


async def test_append_then_update_same_tick_reads_after_append(
    store, client, tmp_store
):
    """결합: 같은 틱에 append + update 면 append 를 먼저 올린 뒤 읽으므로 갱신이 성공한다."""
    store_module.bookmark_upload_queue.append(
        ["U1", "U9", "1.0", "", "active", "t", "t"]
    )
    store_module.bookmark_update_queue.append(_bookmark("U1", "1.0"))
    client.batch_get.return_value = [[["U1", "U9", "1.0"]]]

    report = await store.upload_queue(now=Clock())

    names = [c[0] for c in client.method_calls]
    assert (
        names.index("bulk_upload")
        < names.index("batch_get")
        < names.index("batch_update")
    )
    assert report.skipped == []


# ---------------------------------------------------------------------------
# 요청 예산
# ---------------------------------------------------------------------------


async def test_budget_defers_later_tables_and_keeps_their_queues(
    store, client, tmp_store, monkeypatch
):
    """⚠️ 예산을 넘기면 뒤 테이블은 이월하고 큐를 지우지 않는다."""
    monkeypatch.setattr(store_module, "MAX_REQUESTS_PER_TICK", 1)
    store_module.content_upload_queue.append(["a"])
    store_module.bookmark_upload_queue.append(["b"])

    report = await store.upload_queue(now=Clock())

    client.bulk_upload.assert_called_once_with("contents", [["a"]])
    assert "bookmark" in report.deferred
    assert store_module.bookmark_upload_queue == [["b"]]
    assert store_module.content_upload_queue == []


async def test_budget_exactly_at_limit_is_not_deferred(
    store, client, tmp_store, monkeypatch
):
    """🌀 정확히 상한만큼 쓰는 틱은 이월이 없다."""
    monkeypatch.setattr(store_module, "MAX_REQUESTS_PER_TICK", 2)
    store_module.content_upload_queue.append(["a"])
    store_module.bookmark_upload_queue.append(["b"])

    report = await store.upload_queue(now=Clock())

    assert report.deferred == []
    assert report.requests == 2


async def test_normal_full_tick_stays_under_budget(store, client, tmp_store):
    """결합: 모든 큐 + 갱신 3종 + WP 가 한 틱에 와도 요청 ≤ 11 (< 예산 20, 분당 33 < 60)."""
    store_module.content_upload_queue.append(["c"])
    store_module.bookmark_upload_queue.append(["b"])
    store_module.coffee_chat_proof_upload_queue.append(["p"])
    store_module.point_history_upload_queue.append(["h"])
    store_module.paper_plane_upload_queue.append(["a"])
    store_module.subscription_upload_queue.append(["s"])
    store_module.bookmark_update_queue.append(_bookmark("U1", "1.0"))
    store_module.subscription_update_queue.append(
        {"id": "S1", "a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6}
    )
    store_module.user_update_queue.append(["U1", "n", "c", "C", "i", "10기"])
    store_module.writing_participation_dirty = True
    client.batch_get.return_value = [[["U1", "x", "1.0"]], [["S1"]], [["U1"]]]

    report = await store.upload_queue(now=Clock())

    assert (
        report.requests <= 11
    )  # append 6 + 갱신 읽기1·쓰기1 + WP 읽기1·resize1·update1
    assert report.deferred == []
    assert MAX_REQUESTS_PER_TICK >= report.requests


# ---------------------------------------------------------------------------
# writing_participation: replace_table 1회
# ---------------------------------------------------------------------------


async def test_wp_dirty_merges_and_replaces_once(store, client, tmp_store):
    """✅ dirty → 시트 읽기 1 + replace_table 1회 (clear/bulk_upload 안 씀)."""
    rows = [
        ["user_id", "name", "created_at", "is_writing_participation"],
        ["U1", "a", "t", "True"],
    ]
    with (tmp_store / f"{WP}.csv").open("w", newline="", encoding="utf-8") as f:
        csv.writer(f, quoting=csv.QUOTE_ALL).writerows(rows)
    store_module.writing_participation_dirty = True

    await store.upload_queue(now=Clock())

    client.replace_table.assert_called_once_with(WP, rows)
    client.clear.assert_not_called()
    assert store_module.writing_participation_dirty is False


async def test_wp_replace_failure_restores_dirty(store, client, tmp_store):
    """⚠️ replace 실패 → dirty 복구해 다음 틱 재시도."""
    store_module.writing_participation_dirty = True
    client.replace_table.side_effect = RuntimeError("x")

    with pytest.raises(RuntimeError):
        await store.upload_queue(now=Clock())

    assert store_module.writing_participation_dirty is True


# ---------------------------------------------------------------------------
# 알림 정책 (순수 함수)
# ---------------------------------------------------------------------------


def test_alerts_quota_silent_below_level_3():
    """🌀 429 1~2회는 조용히 백오프만 (알림 스팸 방지)."""
    assert flush_alerts(error=SheetQuotaExceeded(retry_after=60, level=1)) == []
    assert flush_alerts(error=SheetQuotaExceeded(retry_after=120, level=2)) == []


def test_alerts_quota_at_level_3():
    """⚠️ 3회째 지속되면 알림 1건, 초 단위 안내 포함."""
    alerts = flush_alerts(error=SheetQuotaExceeded(retry_after=240, level=3))
    assert len(alerts) == 1
    assert "429" in alerts[0] and "240" in alerts[0]


def test_alerts_skipped_items():
    """⚠️ 못 찾아 건너뛴 항목이 있으면 알림 (데이터 어긋남 신호)."""
    alerts = flush_alerts(
        report=FlushReport(skipped=["users:U1", "bookmark:('U2', '1.0')"])
    )
    assert len(alerts) == 1
    assert "2" in alerts[0] and "users:U1" in alerts[0]


def test_alerts_deferred_is_edge_triggered():
    """🌀 이월은 시작될 때 1회만. 계속 이월 중이면 반복 알림 없음, 해소 후 재발 시 다시."""
    r = FlushReport(deferred=["bookmark"])
    assert len(flush_alerts(report=r, prev_deferred=False)) == 1
    assert flush_alerts(report=r, prev_deferred=True) == []
    assert flush_alerts(report=FlushReport(), prev_deferred=True) == []


def test_alerts_none_on_clean_tick():
    """✅ 정상 틱은 알림 0."""
    assert flush_alerts(report=FlushReport(requests=5)) == []


# ---------------------------------------------------------------------------
# 리뷰 반영 (교차검증 2026-09-08)
# ---------------------------------------------------------------------------


async def test_queues_are_snapshotted_before_any_await(store, client, tmp_store):
    """🌀 틱 도중(await 지점) 들어온 '생성 + 즉시 취소'는 둘 다 다음 틱으로. 갱신만 먼저 처리돼
    시트에서 못 찾고 버려지는 일이 없어야 한다."""
    store_module.content_upload_queue.append(["c"])

    def arrive_during_upload(*_a, **_k):
        store_module.bookmark_upload_queue.append(
            ["U1", "U9", "1.0", "", "active", "t", "t"]
        )
        store_module.bookmark_update_queue.append(_bookmark("U1", "1.0"))

    client.bulk_upload.side_effect = arrive_during_upload

    report = await store.upload_queue(now=Clock())

    client.batch_get.assert_not_called()
    assert report.skipped == []
    assert len(store_module.bookmark_upload_queue) == 1
    assert len(store_module.bookmark_update_queue) == 1

    # 다음 틱: append 가 먼저 올라가고 그 다음 갱신이 성공한다
    client.bulk_upload.side_effect = None
    client.batch_get.return_value = [[["U1", "U9", "1.0"]]]
    report = await store.upload_queue(now=Clock())
    assert report.skipped == []
    assert store_module.bookmark_update_queue == []


async def test_duplicate_keys_in_sheet_update_every_matching_row(
    store, client, tmp_store
):
    """🌀 시트에 같은 키 행이 둘이면(재북마크) 둘 다 같은 값으로 쓴다. 로컬 동작과 일치."""
    store_module.user_update_queue.append(["U1", "n", "c", "C", "i", "10기"])
    client.batch_get.return_value = [[["U1"], ["U1"]]]

    await store.upload_queue(now=Clock())

    data = client.batch_update.call_args.args[0]
    assert [d["range"] for d in data] == ["users!A2:F2", "users!A3:F3"]
    assert data[0]["values"] == data[1]["values"]


async def test_batch_get_short_response_raises_and_keeps_queue(
    store, client, tmp_store
):
    """⚠️ 요청한 범위보다 적게 오면 조용히 이월하지 않고 실패시킨다. 큐는 보존."""
    store_module.user_update_queue.append(["U1", "n", "c", "C", "i", "10기"])
    store_module.subscription_update_queue.append(
        {"id": "S1", "a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6}
    )
    client.batch_get.return_value = [[["S1"]]]  # 2개 요청, 1개만 응답

    with pytest.raises(ValueError):
        await store.upload_queue(now=Clock())

    assert len(store_module.user_update_queue) == 1
    assert len(store_module.subscription_update_queue) == 1


async def test_success_clears_backoff_until_too(store, client, tmp_store):
    """🌀 force 로 창 안에서 성공하면 until 도 지워져 다음 정규 틱이 건너뛰지 않는다."""
    store_module.content_upload_queue.append(["a"])
    client.bulk_upload.side_effect = [_api_error(429), None, None]
    clock = Clock()
    with pytest.raises(SheetQuotaExceeded):
        await store.upload_queue(now=clock)
    clock.t += 5
    store_module.content_upload_queue.append(["b"])
    await store.upload_queue(force=True, now=clock)

    assert store_module._backoff_until == 0.0
    store_module.content_upload_queue.append(["c"])
    report = await store.upload_queue(now=clock)  # 여전히 옛 창 안의 시각
    assert report.backed_off is False
    assert store_module.content_upload_queue == []


def test_next_prev_deferred_ignores_backed_off_ticks():
    """🌀 백오프 틱은 이월 상태를 건드리지 않는다 (이월 중에 '시작' 알림 재발 방지)."""
    assert next_prev_deferred(FlushReport(deferred=["x"]), prev=False) is True
    assert next_prev_deferred(FlushReport(), prev=True) is False
    assert next_prev_deferred(FlushReport(backed_off=True), prev=True) is True
    assert next_prev_deferred(FlushReport(backed_off=True), prev=False) is False


# --- writing_participation 병합 (배포 겹침 구간에 옛 인스턴스가 늦게 올린 행 보존) ---

H = ["user_id", "name", "created_at", "is_writing_participation"]


def test_merge_union_by_user_id_local_first_then_remote_only():
    """✅ 로컬 행 순서 유지 + 시트에만 있는 행을 뒤에 붙인다."""
    local = [H, ["U1", "a", "t1", "True"]]
    remote = [H, ["U1", "a-old", "t0", "True"], ["U2", "b", "t2", "True"]]

    assert merge_writing_participation(local, remote) == [
        H,
        ["U1", "a", "t1", "True"],
        ["U2", "b", "t2", "True"],
    ]


def test_merge_local_wins_on_conflict():
    """✅ 같은 user_id 는 로컬 값."""
    local = [H, ["U1", "new", "t", "True"]]
    remote = [H, ["U1", "old", "t", "False"]]
    assert merge_writing_participation(local, remote)[1] == ["U1", "new", "t", "True"]


def test_merge_empty_remote_and_empty_local():
    """🌀 시트가 비었으면 로컬 그대로, 로컬이 비었으면 헤더 + 시트."""
    local = [H, ["U1", "a", "t", "True"]]
    assert merge_writing_participation(local, []) == local
    assert merge_writing_participation([], [H, ["U2", "b", "t", "True"]]) == [
        H,
        ["U2", "b", "t", "True"],
    ]
    assert merge_writing_participation([], []) == [H]


def test_merge_ignores_remote_short_or_blank_rows_and_dupes():
    """⚠️ 시트의 짧은 행·빈 행·중복 user_id 는 첫 번째만, 짧은 건 버린다."""
    local = [H]
    remote = [H, [], ["U2"], ["U3", "c", "t", "True"], ["U3", "c2", "t", "True"]]
    assert merge_writing_participation(local, remote) == [H, ["U3", "c", "t", "True"]]


async def test_wp_flush_writes_merged_rows_back_to_local(store, client, tmp_store):
    """결합: dirty flush 가 시트 전용 행을 로컬 CSV 에도 남겨 복원과 일관되게 만든다."""
    with (tmp_store / f"{WP}.csv").open("w", newline="", encoding="utf-8") as f:
        csv.writer(f, quoting=csv.QUOTE_ALL).writerows([H, ["U1", "a", "t", "True"]])
    client.get_values.return_value = [H, ["U2", "b", "t", "True"]]
    store_module.writing_participation_dirty = True

    report = await store.upload_queue(now=Clock())

    merged = [H, ["U1", "a", "t", "True"], ["U2", "b", "t", "True"]]
    client.replace_table.assert_called_once_with(WP, merged)
    with (tmp_store / f"{WP}.csv").open(newline="", encoding="utf-8") as f:
        assert list(csv.reader(f, quoting=csv.QUOTE_ALL)) == merged
    assert report.requests == 3  # 읽기 1 + resize 1 + update 1
