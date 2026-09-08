"""ts_to_dt: 슬랙 ts → KST 벽시계 naive datetime (worklog 021).

옛 서버는 KST 였고 Koyeb 컨테이너는 UTC 다. naive fromtimestamp 는 프로세스 TZ 를 따르므로
00~09시 KST 이벤트의 날짜가 하루 어긋난다. 명시적 KST 로 계산해 TZ 와 무관하게 옛 값과 같게 한다.
개발 Mac 이 KST 라 옛 코드로도 통과해 버리므로, 프로세스 TZ 를 UTC 로 강제해 검증한다.
"""

from __future__ import annotations

import datetime
import os
import time

import pytest

from app.utils import ts_to_dt


@pytest.fixture
def utc_process_tz():
    old = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    yield
    if old is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = old
    time.tzset()


def test_epoch_zero_is_kst_nine_oclock(utc_process_tz) -> None:
    """✅ TZ=UTC 프로세스에서도 1970-01-01 09:00 (KST)."""
    assert ts_to_dt("0") == datetime.datetime(1970, 1, 1, 9, 0, 0)


def test_returns_naive_datetime(utc_process_tz) -> None:
    """🌀 BigQuery DATETIME/기존 strftime 호환을 위해 tzinfo 는 없다 (KST 벽시계)."""
    assert ts_to_dt("1700000000.000200").tzinfo is None


def test_date_boundary_uses_kst_not_process_tz(utc_process_tz) -> None:
    """⚠️ 2023-11-14T22:13:20Z 는 KST 로 15일. UTC 컨테이너에서도 15일이어야 한다."""
    assert ts_to_dt("1700000000.000200").date() == datetime.date(2023, 11, 15)


def test_fractional_ts_keeps_microseconds() -> None:
    """🌀 슬랙 ts 의 소수부(마이크로초) 보존."""
    assert ts_to_dt("1700000000.000200").microsecond == 200


def test_non_numeric_raises() -> None:
    """⚠️ 숫자가 아니면 ValueError (기존 동작)."""
    with pytest.raises(ValueError):
        ts_to_dt("abc")
