"""Store 의 시트 동기화 확장 테스트 (Koyeb 이행 견고화, 2026-09-07).

- writing_participation 을 시트에 동기화한다. 기존엔 로컬 전용이라 디스크 초기화 시 유실됐다.
  기존 행을 갱신하는 테이블이라 append 전용 큐가 맞지 않아 clear + 전체 업로드로 간다.
- 부팅 시 로컬 CSV 가 없거나 0바이트인 테이블만 시트에서 복원한다 (restore_missing_tables).
  무조건 pull_all 은 디스크 유지 서버에서 시트(20초 뒤처진 사본)로 로컬(원본)을 덮어써
  유실을 만들 수 있으므로 쓰지 않는다.
"""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app import store as store_module
from app.store import Store

WP = "writing_participation"
WP_HEADER = ["user_id", "name", "created_at", "is_writing_participation"]


@pytest.fixture(autouse=True)
def _reset_module_state():
    """모듈 전역 큐/플래그를 비워 다른 테스트의 잔여물이 섞이지 않게 한다."""
    queue_names = [
        n
        for n in dir(store_module)
        if n.endswith("_queue") and isinstance(getattr(store_module, n), list)
    ]

    def reset() -> None:
        for n in queue_names:
            setattr(store_module, n, [])
        store_module.writing_participation_dirty = False

    reset()
    yield
    reset()


@pytest.fixture
def client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def store(client: MagicMock) -> Store:
    return Store(client=client)


def _rows(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.reader(f, quoting=csv.QUOTE_ALL))


def _write_rows(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f, quoting=csv.QUOTE_ALL).writerows(rows)


# ---------------------------------------------------------------------------
# pull (시트 → 로컬)
# ---------------------------------------------------------------------------


def test_pull_writing_participation_writes_sheet_values_to_local(
    store, client, tmp_store
) -> None:
    """✅ 시트 값(헤더 포함)을 로컬 CSV 에 그대로 쓴다."""
    rows = [WP_HEADER, ["U1", "홍길동", "2026-01-01 00:00:00", "True"]]
    client.get_values.return_value = rows

    store.pull_writing_participation()

    client.get_values.assert_called_once_with(WP)
    assert _rows(tmp_store / f"{WP}.csv") == rows


def test_pull_all_includes_writing_participation(store, client, tmp_store) -> None:
    """✅ 관리자 '전체' 동기화(pull_all)도 새 테이블을 포함한다."""
    client.get_values.return_value = [["h"]]

    store.pull_all()

    pulled = {c.args[0] for c in client.get_values.call_args_list}
    assert WP in pulled


# ---------------------------------------------------------------------------
# upload (로컬 → 시트)
# ---------------------------------------------------------------------------


def test_upload_writing_participation_clears_then_uploads_full_file(
    store, client, tmp_store
) -> None:
    """✅ 갱신 테이블이므로 clear 후 로컬 파일 전체(헤더 포함)를 올린다. 순서가 중요."""
    rows = [WP_HEADER, ["U1", "a", "t", "True"], ["U2", "b", "t", "True"]]
    _write_rows(tmp_store / f"{WP}.csv", rows)

    store.upload_writing_participation()

    client.clear.assert_called_once_with(WP)
    client.bulk_upload.assert_called_once_with(WP, rows)
    names = [c[0] for c in client.method_calls]
    assert names.index("clear") < names.index("bulk_upload")


async def test_upload_queue_flushes_when_dirty(store, client, tmp_store) -> None:
    """✅ dirty 플래그가 켜져 있으면 upload_queue 가 전체 업로드하고 플래그를 내린다."""
    store_module.writing_participation_dirty = True

    await store.upload_queue()

    client.clear.assert_called_once_with(WP)
    client.bulk_upload.assert_called_once()
    assert store_module.writing_participation_dirty is False


async def test_upload_queue_skips_when_not_dirty(store, client, tmp_store) -> None:
    """🌀 dirty 가 아니면 시트를 건드리지 않는다 (불필요한 API 호출 0)."""
    await store.upload_queue()

    client.clear.assert_not_called()
    client.bulk_upload.assert_not_called()


async def test_upload_queue_restores_dirty_flag_on_failure(
    store, client, tmp_store
) -> None:
    """⚠️ 업로드 실패 시 플래그를 되살려 다음 주기에 재시도한다 (유실 방지)."""
    store_module.writing_participation_dirty = True
    client.clear.side_effect = RuntimeError("quota")

    with pytest.raises(RuntimeError):
        await store.upload_queue()

    assert store_module.writing_participation_dirty is True


# ---------------------------------------------------------------------------
# restore_missing_tables (부팅 시 복원)
# ---------------------------------------------------------------------------


def test_restore_pulls_only_missing_tables(store, client, tmp_store) -> None:
    """✅ 파일이 없는 테이블만 시트에서 복원하고, 있는 테이블은 바이트 하나도 건드리지 않는다."""
    (tmp_store / "users.csv").unlink()
    contents_before = (tmp_store / "contents.csv").read_bytes()
    client.get_values.return_value = [["user_id"], ["U1"]]

    restored = store.restore_missing_tables()

    assert restored == ["users"]
    assert (tmp_store / "users.csv").exists()
    assert (tmp_store / "contents.csv").read_bytes() == contents_before
    client.get_values.assert_called_once_with("users")


def test_restore_treats_zero_length_file_as_missing(store, client, tmp_store) -> None:
    """🌀 0바이트 파일도 없는 것으로 보고 복원한다."""
    (tmp_store / f"{WP}.csv").write_bytes(b"")
    client.get_values.return_value = [WP_HEADER]

    assert store.restore_missing_tables() == [WP]


def test_restore_noop_when_everything_present(store, client, tmp_store) -> None:
    """🌀 전부 있으면(헤더만 있어도) 아무것도 하지 않는다. 디스크 유지 서버의 평소 부팅."""
    assert store.restore_missing_tables() == []
    client.get_values.assert_not_called()


def test_restore_propagates_sheet_error(store, client, tmp_store) -> None:
    """⚠️ 시트 읽기 실패는 호출자(startup)가 관리자에게 알릴 수 있게 그대로 올린다."""
    (tmp_store / "users.csv").unlink()
    client.get_values.side_effect = RuntimeError("quota")

    with pytest.raises(RuntimeError):
        store.restore_missing_tables()
