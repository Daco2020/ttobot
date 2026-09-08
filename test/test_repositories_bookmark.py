"""SlackRepository.update_bookmark 는 user_id + content_ts 로만 갱신한다 (worklog 021).

기존엔 content_ts 만 봐서, 같은 글을 북마크한 다른 사용자의 북마크까지 DELETED 됐다.
"""

from __future__ import annotations

import csv
from pathlib import Path

from app import models
from app.slack.repositories import SlackRepository

HEADER = [
    "user_id",
    "content_user_id",
    "content_ts",
    "note",
    "status",
    "created_at",
    "updated_at",
]
ACTIVE = models.BookmarkStatusEnum.ACTIVE
DELETED = models.BookmarkStatusEnum.DELETED


def _row(user_id: str, content_ts: str, status=ACTIVE, note: str = "") -> dict:
    return {
        "user_id": user_id,
        "content_user_id": "U_AUTHOR",
        "content_ts": content_ts,
        "note": note,
        "status": status.value,
        "created_at": "t0",
        "updated_at": "t0",
    }


def _read(tmp_store: Path) -> list[dict]:
    with (tmp_store / "bookmark.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_cancel_touches_only_target_users_row(tmp_store, csv_writer_helper) -> None:
    """⚠️ 기존 버그: 다른 사용자의 같은 글 북마크는 그대로여야 한다."""
    csv_writer_helper(
        tmp_store / "bookmark.csv", HEADER, [_row("U1", "ts1"), _row("U2", "ts1")]
    )

    SlackRepository().update_bookmark("U1", "ts1", new_status=DELETED)

    after = {(r["user_id"], r["content_ts"]): r for r in _read(tmp_store)}
    assert after[("U1", "ts1")]["status"] == DELETED.value
    assert after[("U2", "ts1")]["status"] == ACTIVE.value
    assert after[("U2", "ts1")]["updated_at"] == "t0"


def test_note_update_only_for_target(tmp_store, csv_writer_helper) -> None:
    """✅ 메모 수정은 대상 행의 note·updated_at 만 바꾼다."""
    csv_writer_helper(
        tmp_store / "bookmark.csv", HEADER, [_row("U1", "ts1"), _row("U1", "ts2")]
    )

    SlackRepository().update_bookmark("U1", "ts1", new_note="메모")

    after = {r["content_ts"]: r for r in _read(tmp_store)}
    assert after["ts1"]["note"] == "메모" and after["ts1"]["updated_at"] != "t0"
    assert after["ts2"]["note"] == "" and after["ts2"]["updated_at"] == "t0"


def test_rebookmarked_duplicate_rows_of_same_user_all_updated(
    tmp_store, csv_writer_helper
) -> None:
    """🌀 취소 후 재북마크로 같은 user+글 행이 둘이면 둘 다 갱신 (시트 갱신과 동일)."""
    csv_writer_helper(
        tmp_store / "bookmark.csv",
        HEADER,
        [_row("U1", "ts1", DELETED), _row("U1", "ts1", ACTIVE), _row("U2", "ts1")],
    )

    SlackRepository().update_bookmark("U1", "ts1", new_status=DELETED)

    rows = _read(tmp_store)
    assert [r["status"] for r in rows if r["user_id"] == "U1"] == [
        DELETED.value,
        DELETED.value,
    ]
    assert [r["status"] for r in rows if r["user_id"] == "U2"] == [ACTIVE.value]


def test_no_matching_row_leaves_file_unchanged(tmp_store, csv_writer_helper) -> None:
    """🌀 해당 사용자에게 그 글 북마크가 없으면 아무 행도 바뀌지 않는다."""
    csv_writer_helper(tmp_store / "bookmark.csv", HEADER, [_row("U2", "ts1")])
    before = _read(tmp_store)

    SlackRepository().update_bookmark("U1", "ts1", new_status=DELETED)

    assert _read(tmp_store) == before
