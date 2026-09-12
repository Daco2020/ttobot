"""app.table_cache: CSV 표 메모리 캐시 (worklog 023).

가설 (성공 / 실패 / 엣지 × 단위 / 결합)
- 파일이 그대로면 다시 파싱하지 않는다. (inode·크기·수정 시각) 중 하나라도 바뀌면 다시 읽는다.
- 방금 바뀐 파일(RACY_WINDOW_NS 안)은 믿지 않는다. 읽는 도중 바뀐 결과는 캐시에 넣지 않는다.
- 행 해석은 csv.DictReader 와 같다 (빈 줄 건너뜀, 짧은 행 None, 긴 행은 None 키).
- append_row 는 기존 csv.writer 와 같은 바이트를 쓰고, 크기가 맞을 때만 캐시에 바로 넣는다.
  캐시에 넣은 행 == 디스크를 새로 읽은 행 (round-trip).
"""

from __future__ import annotations

import csv
import os
import time
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from app import table_cache

HEADER = ["user_id", "reason", "point"]


@pytest.fixture(autouse=True)
def _clean_cache():
    table_cache.clear()
    yield
    table_cache.clear()


def _write(path: Path, rows: list[list[str]], header: list[str] = HEADER) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(header)
        writer.writerows(rows)


def _append_external(path: Path, row: list[str]) -> None:
    """앱 밖(시트 복원 등)에서 한 줄 추가한 것처럼 쓴다."""
    with path.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f, quoting=csv.QUOTE_ALL).writerow(row)


def _age(path: Path, seconds: int = 60) -> None:
    """수정 시각을 과거로 돌려 '방금 바뀐 파일' 규칙에 걸리지 않게 한다."""
    ns = time.time_ns() - seconds * 1_000_000_000
    os.utime(path, ns=(ns, ns))


def _fresh(path: Path) -> table_cache.Table:
    """캐시를 거치지 않은 디스크 파싱 결과."""
    return table_cache._parse(str(path))


@pytest.fixture
def csv_path(tmp_path: Path) -> Path:
    path = tmp_path / "t.csv"
    _write(
        path, [["U1", "글 제출", "100"], ["U2", "커피챗", "50"], ["U1", "공지", "20"]]
    )
    _age(path)
    return path


# ---------------------------------------------------------------------------
# 읽기
# ---------------------------------------------------------------------------


def test_read_table_parses_header_and_rows(csv_path: Path) -> None:
    """✅ 헤더와 행을 파일 순서대로 읽는다."""
    table = table_cache.read_table(str(csv_path))

    assert table.header == ("user_id", "reason", "point")
    assert table.rows == (
        ("U1", "글 제출", "100"),
        ("U2", "커피챗", "50"),
        ("U1", "공지", "20"),
    )


def test_unchanged_file_is_parsed_once(csv_path: Path, mocker: MockerFixture) -> None:
    """✅ 파일이 그대로면 두 번째 읽기는 파싱하지 않는다."""
    parse = mocker.spy(table_cache, "_parse")

    first = table_cache.read_table(str(csv_path))
    second = table_cache.read_table(str(csv_path))

    assert parse.call_count == 1
    assert second is first


def test_size_change_reloads(csv_path: Path) -> None:
    """✅ 밖에서 한 줄 추가되면(크기 변화) 다시 읽는다."""
    table_cache.read_table(str(csv_path))
    _append_external(csv_path, ["U3", "큐레이션", "10"])
    _age(csv_path, seconds=30)

    table = table_cache.read_table(str(csv_path))

    assert table.rows[-1] == ("U3", "큐레이션", "10")


def test_same_size_rewrite_with_new_mtime_reloads(csv_path: Path) -> None:
    """✅ 크기가 같은 재작성도 수정 시각이 바뀌면 다시 읽는다."""
    table_cache.read_table(str(csv_path))
    _write(
        csv_path,
        [["U9", "글 제출", "100"], ["U2", "커피챗", "50"], ["U1", "공지", "20"]],
    )
    _age(csv_path, seconds=30)

    table = table_cache.read_table(str(csv_path))

    assert table.rows[0] == ("U9", "글 제출", "100")


def test_recently_modified_file_is_not_trusted(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """⚠️ 방금 쓴 파일은 같은 틈의 같은 크기 재작성을 못 알아채므로 매번 다시 읽는다."""
    path = tmp_path / "fresh.csv"
    _write(path, [["U1", "글 제출", "100"]])
    parse = mocker.spy(table_cache, "_parse")

    table_cache.read_table(str(path))
    _write(path, [["U2", "글 제출", "100"]])
    table = table_cache.read_table(str(path))

    assert parse.call_count == 2
    assert table.rows == (("U2", "글 제출", "100"),)


def test_file_changed_during_read_is_not_cached(
    csv_path: Path, mocker: MockerFixture
) -> None:
    """⚠️ 읽는 도중 파일이 바뀌면 그 결과는 캐시에 넣지 않는다. 다음 읽기에서 새로 읽는다."""
    original_parse = table_cache._parse
    parsed: list[str] = []

    def parse_while_someone_appends(path: str) -> table_cache.Table:
        table = original_parse(path)
        if not parsed:
            _append_external(Path(path), ["U3", "큐레이션", "10"])
            _age(Path(path), seconds=30)
        parsed.append(path)
        return table

    mocker.patch.object(table_cache, "_parse", side_effect=parse_while_someone_appends)

    first = table_cache.read_table(str(csv_path))
    second = table_cache.read_table(str(csv_path))

    assert len(parsed) == 2
    assert first.rows[-1] == ("U1", "공지", "20")
    assert second.rows[-1] == ("U3", "큐레이션", "10")


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    """🌀 파일이 없으면 지금처럼 FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        table_cache.read_table(str(tmp_path / "none.csv"))


def test_empty_file_has_no_header_and_rows(tmp_path: Path) -> None:
    """🌀 0바이트 파일(디스크 초기화 직후 등)은 빈 표."""
    path = tmp_path / "empty.csv"
    path.write_bytes(b"")
    _age(path)

    table = table_cache.read_table(str(path))

    assert table.header == ()
    assert table.rows == ()
    assert table.index("user_id") == {}


def test_rows_as_dicts_match_csv_dictreader(tmp_path: Path) -> None:
    """🌀 빈 줄·짧은 행·긴 행·따옴표 안 줄바꿈까지 csv.DictReader 와 같은 dict 를 만든다."""
    path = tmp_path / "odd.csv"
    path.write_text(
        '"user_id","reason","point"\r\n'
        '"U1","줄\r\n바꿈, 쉼표 ""따옴표""","100"\r\n'
        "\r\n"
        '"U2","짧은 행"\r\n'
        '"U3","긴 행","1","남는 칸"\r\n',
        encoding="utf-8",
        newline="",
    )
    _age(path)

    table = table_cache.read_table(str(path))
    with path.open(encoding="utf-8") as f:
        expected = list(csv.DictReader(f))

    assert [table.to_dict(row) for row in table.rows] == expected
    assert [table.getter("point")(row) for row in table.rows] == [
        row["point"] for row in expected
    ]


def test_to_dict_returns_new_dict_each_time(csv_path: Path) -> None:
    """✅ 호출자가 dict 를 고쳐도 캐시된 행은 그대로다."""
    table = table_cache.read_table(str(csv_path))
    row = table.rows[0]

    table.to_dict(row)["reason"] = "고쳐 씀"

    assert table.to_dict(row)["reason"] == "글 제출"
    assert isinstance(table.rows, tuple)


def test_parse_does_not_hold_extra_copy_of_file(tmp_path: Path) -> None:
    """🌀 파싱 중 파일 전체 문자열을 따로 들지 않는다. 512MB 인스턴스에서 4MB 표를 읽을 때
    임시 메모리가 파일 크기만큼 더 뛰면 안 된다 (재검토: f.read 방식은 표마다 +20MB)."""
    import tracemalloc

    path = tmp_path / "big.csv"
    _write(
        path, [[f"U{i}", "글 제출 포인트 사유 텍스트", str(i)] for i in range(20_000)]
    )
    size = path.stat().st_size

    tracemalloc.start()
    try:
        table = table_cache._parse(str(path))
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert len(table.rows) == 20_000
    assert peak - current < size / 2


def test_same_relative_path_in_other_dir_does_not_mix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """🌀 테스트처럼 cwd 를 옮겨 같은 상대경로를 읽어도 섞이지 않는다 (절대경로 키)."""
    for name, user_id in [("a", "UA"), ("b", "UB")]:
        (tmp_path / name).mkdir()
        _write(tmp_path / name / "t.csv", [[user_id, "글 제출", "100"]])
        _age(tmp_path / name / "t.csv")

    monkeypatch.chdir(tmp_path / "a")
    first = table_cache.read_table("t.csv")
    monkeypatch.chdir(tmp_path / "b")
    second = table_cache.read_table("t.csv")

    assert first.rows[0][0] == "UA"
    assert second.rows[0][0] == "UB"


def test_index_groups_rows_by_column_in_file_order(csv_path: Path) -> None:
    """✅ 열 값별로 파일 순서를 지켜 묶는다."""
    table = table_cache.read_table(str(csv_path))

    index = table.index("user_id")

    assert index["U1"] == (("U1", "글 제출", "100"), ("U1", "공지", "20"))
    assert "U404" not in index


def test_index_on_unknown_column_raises_like_dictreader(csv_path: Path) -> None:
    """⚠️ 없는 열은 DictReader 의 row[열] 처럼 KeyError."""
    table = table_cache.read_table(str(csv_path))

    with pytest.raises(KeyError):
        table.index("없는열")


def test_load_cached_keeps_variants_apart_and_invalidate_drops_all(
    csv_path: Path,
) -> None:
    """✅ 같은 파일을 다른 모양으로 읽는 캐시(예: polars 표)는 따로 두고, invalidate 는 모두 버린다."""
    calls: list[str] = []

    def loader(tag: str):
        def load(path: str) -> str:
            calls.append(tag)
            return f"{tag}:{Path(path).name}"

        return load

    assert table_cache.load_cached(str(csv_path), "a", loader("a")) == "a:t.csv"
    assert table_cache.load_cached(str(csv_path), "b", loader("b")) == "b:t.csv"
    table_cache.load_cached(str(csv_path), "a", loader("a"))
    assert calls == ["a", "b"]

    table_cache.invalidate(str(csv_path))
    table_cache.load_cached(str(csv_path), "a", loader("a"))
    assert calls == ["a", "b", "a"]


def test_invalidate_forces_reload(csv_path: Path, mocker: MockerFixture) -> None:
    """✅ invalidate 뒤에는 파일이 그대로여도 다시 읽는다 (앱 안 재작성 직후용)."""
    table_cache.read_table(str(csv_path))
    parse = mocker.spy(table_cache, "_parse")

    table_cache.invalidate(str(csv_path))
    table_cache.read_table(str(csv_path))

    assert parse.call_count == 1


# ---------------------------------------------------------------------------
# append_row
# ---------------------------------------------------------------------------


def test_append_row_writes_same_bytes_as_csv_writer(tmp_path: Path) -> None:
    """✅ 기존 저장 코드(open 'a' + csv.writer QUOTE_ALL)와 같은 바이트를 쓴다."""
    values = ["U1", '줄\n바꿈, "따옴표"', "100"]
    ours, reference = tmp_path / "ours.csv", tmp_path / "ref.csv"
    for path in (ours, reference):
        _write(path, [])

    table_cache.append_row(str(ours), values)
    with reference.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f, quoting=csv.QUOTE_ALL).writerow(values)

    assert ours.read_bytes() == reference.read_bytes()


def test_append_row_updates_cache_without_reparse(
    csv_path: Path, mocker: MockerFixture
) -> None:
    """✅ 앱이 한 줄 추가하면 캐시와 이미 만든 인덱스에도 바로 넣는다. 다시 파싱하지 않는다."""
    table_cache.read_table(str(csv_path)).index("user_id")
    parse = mocker.spy(table_cache, "_parse")

    table_cache.append_row(str(csv_path), ["U1", "큐레이션", "10"])
    table = table_cache.read_table(str(csv_path))

    assert parse.call_count == 0
    assert table.rows[-1] == ("U1", "큐레이션", "10")
    assert table.index("user_id")["U1"][-1] == ("U1", "큐레이션", "10")


def test_appended_cache_matches_fresh_disk_parse(csv_path: Path) -> None:
    """결합(round-trip): 캐시에 넣은 행 == 디스크를 새로 읽은 행. 줄바꿈 종류·따옴표·한글 포함."""
    table_cache.read_table(str(csv_path))

    table_cache.append_row(str(csv_path), ["U1", 'a "q"\r\nline2\nline3\rend', "x,y"])
    table_cache.append_row(str(csv_path), ["U2", "", "끝"])
    cached = table_cache.read_table(str(csv_path))

    fresh = _fresh(csv_path)
    assert cached.header == fresh.header
    assert cached.rows == fresh.rows


def test_append_row_after_external_change_invalidates(csv_path: Path) -> None:
    """⚠️ 캐시 뒤에 밖에서 먼저 바뀌었으면 캐시에 끼워 넣지 않고 버린다."""
    table_cache.read_table(str(csv_path))
    _append_external(csv_path, ["U3", "밖에서", "1"])

    table_cache.append_row(str(csv_path), ["U4", "앱에서", "2"])
    table = table_cache.read_table(str(csv_path))

    assert table.rows[-2:] == (("U3", "밖에서", "1"), ("U4", "앱에서", "2"))
    assert table.rows == _fresh(csv_path).rows


def test_append_row_to_file_without_trailing_newline_matches_disk(
    tmp_path: Path,
) -> None:
    """⚠️ 마지막 줄바꿈이 없는 파일은 디스크 해석(앞줄에 붙음)을 따른다."""
    path = tmp_path / "no_newline.csv"
    path.write_text(
        '"user_id","reason","point"\r\n"U1","글 제출","100"',
        encoding="utf-8",
        newline="",
    )
    _age(path)
    table_cache.read_table(str(path))

    table_cache.append_row(str(path), ["U2", "커피챗", "50"])

    assert table_cache.read_table(str(path)).rows == _fresh(path).rows


def test_append_row_to_empty_file_matches_disk(tmp_path: Path) -> None:
    """🌀 0바이트 파일에 추가하면 그 줄이 헤더가 된다 (DictReader 와 같게)."""
    path = tmp_path / "empty.csv"
    path.write_bytes(b"")
    _age(path)
    table_cache.read_table(str(path))

    table_cache.append_row(str(path), ["U1", "글 제출", "100"])
    table = table_cache.read_table(str(path))

    assert table.header == ("U1", "글 제출", "100")
    assert table.rows == ()


def test_append_row_without_cache_just_writes(tmp_path: Path) -> None:
    """🌀 캐시가 없거나 파일이 없어도 지금처럼 파일을 만들어 쓴다."""
    path = tmp_path / "new.csv"

    table_cache.append_row(str(path), ["U1", "글 제출", "100"])

    assert path.read_bytes() == '"U1","글 제출","100"\r\n'.encode()


def test_repeated_append_and_read_stay_consistent(csv_path: Path) -> None:
    """멱등: 추가·읽기를 반복해도 행이 빠지거나 겹치지 않는다."""
    table_cache.read_table(str(csv_path))
    for i in range(20):
        table_cache.append_row(str(csv_path), [f"U{i}", "반복", str(i)])
        table_cache.read_table(str(csv_path)).index("user_id")

    cached = table_cache.read_table(str(csv_path))

    assert len(cached.rows) == 3 + 20
    assert cached.rows == _fresh(csv_path).rows
    assert cached.index("user_id")["U1"] == (
        ("U1", "글 제출", "100"),
        ("U1", "공지", "20"),
        ("U1", "반복", "1"),
    )


def test_append_row_after_file_truncated_inside_quotes_matches_disk(
    tmp_path: Path,
) -> None:
    """⚠️ 따옴표 안에서 잘린 파일(쓰기 중 종료 등)은 끝이 줄바꿈이어도 캐시에 이어 붙이지 않는다.
    디스크에선 새 줄이 앞 필드에 먹혀서, 캐시에만 새 행이 있으면 재시작 전후로 조회가 달라진다."""
    path = tmp_path / "truncated.csv"
    path.write_text(
        '"user_id","reason","point"\r\n"U1","글 제출","100"\r\n"U2","잘린\r\n',
        encoding="utf-8",
        newline="",
    )
    _age(path)
    table_cache.read_table(str(path)).index("user_id")

    table_cache.append_row(str(path), ["U3", "새 포인트", "20"])

    table = table_cache.read_table(str(path))
    fresh = _fresh(path)
    assert table.rows == fresh.rows
    assert ("U3" in table.index("user_id")) == ("U3" in fresh.index("user_id"))


def test_append_row_skips_cache_when_other_write_slipped_in(
    csv_path: Path, mocker: MockerFixture
) -> None:
    """⚠️ 쓰기 전후 크기 차이가 이 줄 크기와 다르면(다른 쓰기가 끼면) 캐시에 넣지 않고 다시 읽는다."""
    table_cache.read_table(str(csv_path))
    original = table_cache._extendable_stat

    def stat_then_someone_appends(path: str, entry):
        stat = original(path, entry)
        _append_external(Path(path), ["U9", "끼어든 쓰기", "1"])
        return stat

    mocker.patch.object(
        table_cache, "_extendable_stat", side_effect=stat_then_someone_appends
    )

    table_cache.append_row(str(csv_path), ["U4", "앱에서", "2"])

    rows = table_cache.read_table(str(csv_path)).rows
    assert rows == _fresh(csv_path).rows
    assert rows[-2:] == (("U9", "끼어든 쓰기", "1"), ("U4", "앱에서", "2"))


def test_recent_file_is_not_cached_even_if_rewrite_keeps_file_key(
    tmp_path: Path,
) -> None:
    """⚠️ 2초 규칙: 같은 틈·같은 크기 재작성은 (inode·크기·수정 시각)이 그대로라 키로 못 알아챈다.
    방금 바뀐 파일을 캐시에 넣지 않아야 새 내용이 보인다."""
    path = tmp_path / "fresh.csv"
    _write(path, [["U1", "글 제출", "100"]])
    first = path.stat()
    table_cache.read_table(str(path))

    _write(path, [["U2", "글 제출", "100"]])
    os.utime(path, ns=(first.st_atime_ns, first.st_mtime_ns))
    again = path.stat()
    assert (again.st_ino, again.st_size, again.st_mtime_ns) == (
        first.st_ino,
        first.st_size,
        first.st_mtime_ns,
    )

    assert table_cache.read_table(str(path)).rows == (("U2", "글 제출", "100"),)


def test_repeated_values_in_known_columns_are_shared(tmp_path: Path) -> None:
    """✅ 자주 반복되는 열(user_id·reason 등)의 같은 값은 문자열 하나를 공유한다.
    42,840행 point_histories 에서 약 9MB 를 줄인다 (worklog 025)."""
    path = tmp_path / "shared.csv"
    _write(path, [["U1", "글 제출", "100"], ["U1", "글 제출", "200"]])
    _age(path)

    rows = table_cache.read_table(str(path)).rows

    assert rows[0][0] is rows[1][0]
    assert rows[0][1] is rows[1][1]
    assert rows == (("U1", "글 제출", "100"), ("U1", "글 제출", "200"))


# ---------------------------------------------------------------------------
# warm_up (부팅 때 미리 읽기)
# ---------------------------------------------------------------------------


@pytest.fixture
def recorded_sleeps(mocker: MockerFixture) -> list[float]:
    """warm_up 이 기다리려던 시간을 기록하고 실제로는 기다리지 않는다."""
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    mocker.patch.object(table_cache, "_sleep", new=fake_sleep)
    return sleeps


@pytest.mark.asyncio
async def test_warm_up_reads_tables_and_builds_indexes(
    csv_path: Path, recorded_sleeps: list[float], mocker: MockerFixture
) -> None:
    """✅ 표를 읽고 인덱스까지 만들어 둔다. 이미 가라앉은 파일이면 기다리지 않는다."""
    seconds = await table_cache.warm_up({str(csv_path): ("user_id",)})
    parse = mocker.spy(table_cache, "_parse")

    table = table_cache.read_table(str(csv_path))

    assert parse.call_count == 0
    assert "user_id" in table._indexes
    assert recorded_sleeps == []
    assert seconds >= 0


@pytest.mark.asyncio
async def test_warm_up_waits_for_just_restored_files_to_settle(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """⚠️ 재배치 직후 시트 복원으로 방금 쓴 파일은 2초 규칙에 걸려 캐시에 안 남는다.
    가라앉을 때까지 기다린 뒤 읽어서 캐시에 남긴다."""
    path = tmp_path / "restored.csv"
    _write(path, [["U1", "글 제출", "100"]])
    sleeps: list[float] = []

    async def sleep_and_let_time_pass(seconds: float) -> None:
        sleeps.append(seconds)
        _age(path)

    mocker.patch.object(table_cache, "_sleep", new=sleep_and_let_time_pass)

    await table_cache.warm_up({str(path): ("user_id",)})
    parse = mocker.spy(table_cache, "_parse")
    table_cache.read_table(str(path))

    assert len(sleeps) == 1
    assert 0 < sleeps[0] <= table_cache.RACY_WINDOW_NS / 1_000_000_000 + 0.1
    assert parse.call_count == 0


@pytest.mark.asyncio
async def test_warm_up_wait_is_capped_for_future_mtime(
    csv_path: Path, recorded_sleeps: list[float]
) -> None:
    """🌀 수정 시각이 미래(시계 차이)여도 2초 남짓만 기다리고 끝난다."""
    future = time.time_ns() + 3600 * 1_000_000_000
    os.utime(csv_path, ns=(future, future))

    await table_cache.warm_up({str(csv_path): ("user_id",)})

    assert len(recorded_sleeps) == 1
    assert recorded_sleeps[0] <= table_cache.RACY_WINDOW_NS / 1_000_000_000 + 0.1


@pytest.mark.asyncio
async def test_warm_up_missing_file_raises(
    tmp_path: Path, recorded_sleeps: list[float]
) -> None:
    """⚠️ 파일이 없으면 그대로 올린다. 알리고 부팅을 계속할지는 호출자(startup)가 정한다."""
    with pytest.raises(FileNotFoundError):
        await table_cache.warm_up({str(tmp_path / "none.csv"): ("user_id",)})
