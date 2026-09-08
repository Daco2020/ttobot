"""SpreadSheetClient 의 writing_participation 탭 자동 생성 테스트.

기획: 탭을 새로 추가하기로 함 (사용자 승인 2026-09-07). 탭이 없어도 부팅이 죽지 않도록
자동 생성하고 헤더를 쓴다. 이미 있으면 그대로 쓴다.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from gspread.exceptions import WorksheetNotFound

from app.client import WRITING_PARTICIPATION_HEADER, SpreadSheetClient

WP = "writing_participation"


@pytest.fixture(autouse=True)
def _reset_singleton():
    SpreadSheetClient._instance = None
    yield
    SpreadSheetClient._instance = None


def test_creates_writing_participation_tab_with_header_when_missing() -> None:
    """✅ 탭 없음 → add_worksheet + 헤더 1행."""
    doc = MagicMock()
    created = MagicMock()

    def worksheet(name: str):
        if name == WP:
            raise WorksheetNotFound(name)
        return MagicMock()

    doc.worksheet.side_effect = worksheet
    doc.add_worksheet.return_value = created

    client = SpreadSheetClient(doc=doc)

    doc.add_worksheet.assert_called_once()
    assert doc.add_worksheet.call_args.kwargs["title"] == WP
    # append_row 는 캐시 row_count 만 올려 grid 와 어긋나므로 헤더는 update 로 쓴다
    created.update.assert_called_once_with(
        values=[WRITING_PARTICIPATION_HEADER], range_name="A1"
    )
    created.append_row.assert_not_called()
    assert client._sheets[WP] is created


def test_uses_existing_writing_participation_tab() -> None:
    """🌀 탭 있음 → 생성/헤더 쓰기 없음."""
    doc = MagicMock()
    existing = MagicMock()
    doc.worksheet.side_effect = lambda name: existing if name == WP else MagicMock()

    client = SpreadSheetClient(doc=doc)

    doc.add_worksheet.assert_not_called()
    existing.update.assert_not_called()
    assert client._sheets[WP] is existing
