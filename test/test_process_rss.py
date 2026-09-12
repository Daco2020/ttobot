"""app.utils.process_rss_mb: 운영 메모리를 로그에 남기기 위한 helper (worklog 025).

Koyeb 메모리 그래프가 500MB 근처인데 그중 얼마가 실제 프로세스 메모리인지 알 수 없었다.
부팅·업로드 로그에 한 줄 남겨 추측 없이 보려는 것.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app import utils


def test_reads_vmrss_from_proc_status(tmp_path: Path) -> None:
    """✅ 리눅스 /proc/self/status 의 VmRSS(kB)를 MB 로 바꾼다."""
    status = tmp_path / "status"
    status.write_text("Name:\tpython3\nVmRSS:\t  307200 kB\nThreads:\t9\n")

    assert utils.process_rss_mb(str(status)) == pytest.approx(300.0)


def test_falls_back_when_proc_status_missing(tmp_path: Path) -> None:
    """🌀 /proc 이 없는 환경(맥 개발기)에서도 0 보다 큰 값을 준다."""
    assert utils.process_rss_mb(str(tmp_path / "none")) > 0
