"""SpreadSheetClient 배치 API 래퍼 테스트 (worklog 020)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from gspread.exceptions import APIError

from app.client import SpreadSheetClient, is_quota_error


@pytest.fixture(autouse=True)
def _reset_singleton():
    SpreadSheetClient._instance = None
    yield
    SpreadSheetClient._instance = None


@pytest.fixture
def doc() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(doc) -> SpreadSheetClient:
    return SpreadSheetClient(doc=doc)


def _api_error(status: int) -> APIError:
    response = MagicMock()
    response.status_code = status
    response.json.return_value = {
        "error": {"code": status, "message": "m", "status": "S"}
    }
    response.text = "m"
    return APIError(response)


def test_batch_get_returns_values_aligned_with_ranges(client, doc):
    """✅ values_batch_get 1회, 결과를 요청 순서대로 rows 리스트로 정규화."""
    doc.values_batch_get.return_value = {
        "valueRanges": [
            {"range": "a!A2:A", "values": [["1"], ["2"]]},
            {"range": "b!A2:A"},  # 빈 시트는 values 키 자체가 없다
        ]
    }

    out = client.batch_get(["a!A2:A", "b!A2:A"])

    doc.values_batch_get.assert_called_once_with(["a!A2:A", "b!A2:A"])
    assert out == [[["1"], ["2"]], []]


def test_batch_get_empty_ranges_makes_no_request(client, doc):
    """🌀 요청할 범위가 없으면 API 를 부르지 않는다."""
    assert client.batch_get([]) == []
    doc.values_batch_get.assert_not_called()


def test_batch_update_sends_raw_multi_range_body(client, doc):
    """✅ values_batch_update 1회, RAW, 여러 시트 범위를 한 본문에."""
    data = [
        {"range": "users!A3:F3", "values": [["x"]]},
        {"range": "bookmark!A4:G4", "values": [["y"]]},
    ]

    client.batch_update(data)

    body = doc.values_batch_update.call_args.args[0]
    assert body["valueInputOption"] == "RAW"
    assert body["data"] == data


def test_batch_update_empty_makes_no_request(client, doc):
    """🌀 쓸 게 없으면 요청 0."""
    client.batch_update([])
    doc.values_batch_update.assert_not_called()


def test_replace_table_pads_to_row_count_and_updates_once(client, doc):
    """✅ 기존 행 수(row_count)까지 빈 행으로 채워 update 1회 → 잔여행이 지워지고 빈 창이 없다."""
    sheet = MagicMock()
    sheet.row_count = 5
    client._sheets["writing_participation"] = sheet
    values = [["h1", "h2"], ["a", "b"]]

    client.replace_table("writing_participation", values)

    sheet.update.assert_called_once()
    kwargs = sheet.update.call_args.kwargs
    assert kwargs["range_name"] == "A1:B5"
    assert kwargs["values"] == values + [["", ""]] * 3
    sheet.clear.assert_not_called()


def test_replace_table_larger_than_grid_uses_values_length(client, doc):
    """🌀 새 표가 grid 보다 크면 표 크기가 범위."""
    sheet = MagicMock()
    sheet.row_count = 1
    client._sheets["x"] = sheet

    client.replace_table("x", [["h"], ["1"], ["2"]])

    assert sheet.update.call_args.kwargs["range_name"] == "A1:A3"


def test_replace_table_header_only(client, doc):
    """🌀 헤더만 있어도 동작 (데이터 0행)."""
    sheet = MagicMock()
    sheet.row_count = 2
    client._sheets["x"] = sheet

    client.replace_table("x", [["h1", "h2"]])

    assert sheet.update.call_args.kwargs["values"] == [["h1", "h2"], ["", ""]]


def test_is_quota_error_only_for_429():
    """⚠️ 429 만 한도 초과. 403·500·일반 예외는 아니다."""
    assert is_quota_error(_api_error(429)) is True
    assert is_quota_error(_api_error(403)) is False
    assert is_quota_error(_api_error(500)) is False
    assert is_quota_error(RuntimeError("x")) is False
