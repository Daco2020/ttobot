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


def test_replace_table_resizes_to_values_then_updates(client, doc):
    """✅ 캐시 row_count 를 믿지 않는다. grid 를 표 크기로 resize 한 뒤 update (쓰기 2회).

    gspread append_rows 는 실제 grid 와 무관하게 캐시만 +N 하므로(자동 생성 탭 = 1001 vs 1000)
    캐시 기반 범위는 values.update 에서 400 을 낸다.
    """
    sheet = MagicMock()
    sheet.row_count = 1001  # 드리프트된 캐시
    client._sheets["writing_participation"] = sheet
    values = [["h1", "h2"], ["a", "b"]]

    client.replace_table("writing_participation", values)

    sheet.resize.assert_called_once_with(rows=2, cols=2)
    sheet.update.assert_called_once()
    kwargs = sheet.update.call_args.kwargs
    assert kwargs["range_name"] == "A1:B2"
    assert kwargs["values"] == values  # 패딩 없음
    names = [c[0] for c in sheet.method_calls]
    assert names.index("resize") < names.index("update")
    sheet.clear.assert_not_called()


def test_replace_table_grid_smaller_than_values(client, doc):
    """🌀 grid 가 표보다 작아도 resize 가 키운다."""
    sheet = MagicMock()
    sheet.row_count = 1
    client._sheets["x"] = sheet

    client.replace_table("x", [["h"], ["1"], ["2"]])

    sheet.resize.assert_called_once_with(rows=3, cols=1)
    assert sheet.update.call_args.kwargs["range_name"] == "A1:A3"


def test_replace_table_header_only(client, doc):
    """🌀 헤더만 있어도 1행으로 resize + update."""
    sheet = MagicMock()
    sheet.row_count = 1000
    client._sheets["x"] = sheet

    client.replace_table("x", [["h1", "h2"]])

    sheet.resize.assert_called_once_with(rows=1, cols=2)
    assert sheet.update.call_args.kwargs["values"] == [["h1", "h2"]]


def test_replace_table_empty_values_is_noop(client, doc):
    """🌀 값이 없으면 아무것도 하지 않는다 (grid 를 0 으로 줄이지 않는다)."""
    sheet = MagicMock()
    client._sheets["x"] = sheet

    client.replace_table("x", [])

    sheet.resize.assert_not_called()
    sheet.update.assert_not_called()


def test_is_quota_error_only_for_429():
    """⚠️ 429 만 한도 초과. 403·500·일반 예외는 아니다."""
    assert is_quota_error(_api_error(429)) is True
    assert is_quota_error(_api_error(403)) is False
    assert is_quota_error(_api_error(500)) is False
    assert is_quota_error(RuntimeError("x")) is False
