"""CSV 표 메모리 캐시. 파일이 바뀔 때만 다시 읽는다 (worklog 023).

Koyeb 무료 인스턴스(0.1 vCPU)에서 요청마다 users·contents·point_histories CSV 를 통째로 파싱해
이벤트 루프가 몇 초씩 멈췄다(views.publish 8초 타임아웃, trigger_id 3초 만료). 한 번 읽은 표를
들고 있다가 파일의 (inode, 크기, 수정 시각)이 바뀌면 다시 읽는다.

- 표(Table)는 불변 스냅샷이다. 행은 tuple 이고 모델·dict 는 호출자가 매번 새로 만든다.
- 수정 시각이 방금(RACY_WINDOW_NS 안)인 파일은 캐시에 넣지 않는다. 파일 시각은 수 ms 단위라
  같은 틈에 같은 크기로 다시 쓰이면 바뀐 줄 모른다.
- 읽는 도중 파일이 바뀌면 그 결과는 캐시에 넣지 않는다.
- 이 앱이 한 줄 추가할 때(append_row)는 파일 크기가 계산과 맞으면 캐시에도 바로 이어 붙인다.
  포인트·글이 몰릴 때 매번 통째로 다시 읽지 않기 위해서다.
- 앱 안에서 파일을 통째로 다시 쓰면(pandas to_csv, Store.write) invalidate 를 부른다.
- 부팅 때 warm_up 으로 미리 읽어 두면 재시작 직후 첫 요청도 파싱하지 않는다.
- 이벤트 루프 스레드에서 쓴다. 부팅 중 복원(asyncio.to_thread 안의 Store.write)은 다른 코드가
  캐시를 만지기 전이라 괜찮지만, 요청 처리 중 다른 스레드에서 부르면 안 된다.
"""

from __future__ import annotations

import asyncio
import csv
import io
import os
import sys
import time
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Hashable,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    TypeVar,
)

T = TypeVar("T")
Row = tuple[str, ...]

RACY_WINDOW_NS = 2_000_000_000
_TABLE = "table"

# 값이 반복되는 열. 같은 문자열을 하나로 모으면 point_histories 에서 약 9MB 가 준다.
# id·url·본문처럼 값이 거의 다 다른 열은 넣지 않는다. 모아 둘수록 손해다.
INTERNED_COLUMNS = frozenset(
    {
        "user_id",
        "username",
        "target_user_id",
        "target_user_channel",
        "sender_id",
        "sender_name",
        "receiver_id",
        "receiver_name",
        "channel_id",
        "channel_name",
        "cohort",
        "category",
        "type",
        "reason",
        "status",
        "curation_flag",
        "feedback_intensity",
        "color_label",
        "is_writing_participation",
    }
)


@dataclass(frozen=True)
class Table:
    header: tuple[str, ...]
    rows: tuple[Row, ...]
    # 따옴표 개수가 홀수면 마지막 필드가 따옴표 안에서 잘린 파일이다. 줄을 이어 붙이면
    # 디스크에선 그 줄이 앞 필드에 먹혀서 캐시와 달라진다. 앱이 쓰는 규격 CSV(QUOTE_ALL) 전제라
    # 따옴표를 글자로 넣은 비규격 행이 섞이면 판정이 틀릴 수 있다.
    open_quote: bool = False
    # 열 값은 csv.DictReader 처럼 Any 로 둔다 (짧은 행이면 None).
    _indexes: dict[str, dict[Any, tuple[Row, ...]]] = field(
        default_factory=dict, compare=False, repr=False
    )

    def getter(self, column: str) -> Callable[[Row], Any]:
        """행에서 열 값을 꺼내는 함수. csv.DictReader 의 row[열] 과 같다 (짧은 행은 None).

        없는 열이면 행이 있을 때 KeyError. 같은 이름 열이 여럿이면 DictReader 처럼 마지막 열.
        """
        if column not in self.header:
            if self.rows:
                raise KeyError(column)
            return lambda row: None
        position = len(self.header) - 1 - self.header[::-1].index(column)
        return lambda row: row[position] if position < len(row) else None

    def to_dict(self, row: Row) -> dict[Any, Any]:
        """csv.DictReader 와 같은 규칙으로 dict 를 새로 만든다. 긴 행의 남는 칸은 None 키."""
        record: dict[Any, Any] = dict(zip(self.header, row))
        if len(self.header) < len(row):
            record[None] = list(row[len(self.header) :])
        else:
            for column in self.header[len(row) :]:
                record[column] = None
        return record

    def index(self, column: str) -> dict[Any, tuple[Row, ...]]:
        """열 값별 행 묶음(파일 순서). 처음 부를 때 만들어 둔다. 돌려받은 dict 는 읽기만 한다."""
        if column not in self._indexes:
            value_of = self.getter(column)
            groups: dict[Any, list[Row]] = {}
            for row in self.rows:
                groups.setdefault(value_of(row), []).append(row)
            self._indexes[column] = {key: tuple(rows) for key, rows in groups.items()}
        return self._indexes[column]

    def appended(self, row: Row) -> Table:
        """행 하나를 덧붙인 새 표. 이미 만든 인덱스도 이어 붙인다 (옛 표는 그대로)."""
        table = Table(
            header=self.header, rows=self.rows + (row,), open_quote=self.open_quote
        )
        for column, groups in self._indexes.items():
            if column not in self.header:
                continue
            key = table.getter(column)(row)
            carried = dict(groups)
            carried[key] = groups.get(key, ()) + (row,)
            table._indexes[column] = carried
        return table


@dataclass(frozen=True)
class _Entry:
    key: tuple[int, int, int]
    value: Any


_entries: dict[tuple[str, Hashable], _Entry] = {}


def _key_of(stat: os.stat_result) -> tuple[int, int, int]:
    return (stat.st_ino, stat.st_size, stat.st_mtime_ns)


def _is_settled(stat: os.stat_result) -> bool:
    return time.time_ns() - stat.st_mtime_ns >= RACY_WINDOW_NS


def _parse(path: str) -> Table:
    """저장소 코드가 읽던 대로 텍스트 모드(universal newline)로 줄씩 읽는다. 첫 줄이 헤더, 빈 줄은 건너뛴다.

    따옴표는 줄마다 세어 홀짝만 기록한다. 파일 전체를 문자열로 읽어 세면 파싱 중 임시 메모리가
    표마다 파일 크기의 몇 배(+20MB)로 뛴다.
    """
    quotes = 0

    def counted(lines: Iterable[str]) -> Iterator[str]:
        nonlocal quotes
        for line in lines:
            quotes += line.count('"')
            yield line

    with open(path, encoding="utf-8") as f:
        records = csv.reader(counted(f))
        header = tuple(next(records, ()))
        shared = _shared_positions(header)
        rows = tuple(_shared_row(record, shared) for record in records if record)
    return Table(header=header, rows=rows, open_quote=quotes % 2 == 1)


def _shared_positions(header: tuple[str, ...]) -> tuple[int, ...]:
    """값이 반복되는 열의 자리."""
    return tuple(i for i, column in enumerate(header) if column in INTERNED_COLUMNS)


def _shared_row(record: list[str], shared: tuple[int, ...]) -> Row:
    """반복되는 열은 같은 문자열 객체를 쓰게 한다."""
    row = list(record)
    for index in shared:
        if index < len(row):
            row[index] = sys.intern(row[index])
    return tuple(row)


def load_cached(path: str, variant: Hashable, loader: Callable[[str], T]) -> T:
    """path 를 loader 로 읽은 결과를 파일이 바뀔 때까지 들고 있는다. variant 로 읽는 모양을 구분한다."""
    abspath = os.path.abspath(path)
    cache_key = (abspath, variant)
    before = os.stat(abspath)
    entry = _entries.get(cache_key)
    if entry is not None and entry.key == _key_of(before):
        return entry.value

    # 옛 결과를 먼저 버려 큰 표가 메모리에 두 벌 올라가지 않게 한다.
    _entries.pop(cache_key, None)
    value = loader(abspath)
    after = os.stat(abspath)
    if _key_of(after) == _key_of(before) and _is_settled(after):
        _entries[cache_key] = _Entry(key=_key_of(after), value=value)
    return value


def read_table(path: str) -> Table:
    """CSV 를 표로 읽는다. 파일이 그대로면 파싱하지 않는다."""
    return load_cached(path, _TABLE, _parse)


def append_row(path: str, values: list[str]) -> None:
    """기존 저장 코드(open 'a' + csv.writer QUOTE_ALL)와 같은 바이트로 한 줄 추가한다.

    캐시가 있고 그 뒤로 파일이 안 바뀌었으면 캐시에도 이어 붙인다. 쓰기 전 파일이 비었거나
    줄바꿈으로 끝나지 않거나 따옴표 안에서 잘렸으면(디스크에선 헤더가 되거나 앞줄에 붙는다)
    캐시를 버린다.
    """
    abspath = os.path.abspath(path)
    buffer = io.StringIO()
    csv.writer(buffer, quoting=csv.QUOTE_ALL).writerow(values)
    data = buffer.getvalue()

    # 쓰는 동안은 캐시에서 뺀다. 도중에 실패하면 빠진 채로 남아 다음 읽기가 새로 읽는다.
    entry = _entries.pop((abspath, _TABLE), None)
    before = _extendable_stat(abspath, entry)

    with open(abspath, "a", newline="", encoding="utf-8") as f:
        f.write(data)

    if entry is None or before is None:
        return
    after = os.stat(abspath)
    if after.st_ino != before.st_ino or after.st_size != before.st_size + len(
        data.encode("utf-8")
    ):
        return  # 그 사이 다른 쓰기가 끼었다.

    # 디스크를 읽을 때와 같게 universal newline 으로 해석한다 (따옴표 안 \r\n → \n).
    record = next(csv.reader(io.StringIO(data, newline=None)), [])
    shared = _shared_positions(entry.value.header)
    table = entry.value.appended(_shared_row(record, shared)) if record else entry.value
    _entries[(abspath, _TABLE)] = _Entry(key=_key_of(after), value=table)


def _extendable_stat(path: str, entry: _Entry | None) -> os.stat_result | None:
    """캐시에 이어 붙여도 되는 상태면 쓰기 전 stat 을, 아니면 None."""
    if entry is None or entry.value.open_quote:
        return None
    try:
        stat = os.stat(path)
    except FileNotFoundError:
        return None
    if _key_of(stat) != entry.key or stat.st_size == 0:
        return None
    with open(path, "rb") as f:
        f.seek(-1, os.SEEK_END)
        if f.read(1) != b"\n":
            return None
    return stat


def invalidate(path: str) -> None:
    """앱 안에서 파일을 통째로 다시 쓴 뒤 부른다. 그 파일의 캐시를 모두 버린다."""
    abspath = os.path.abspath(path)
    for cache_key in [key for key in _entries if key[0] == abspath]:
        del _entries[cache_key]


def clear() -> None:
    """모든 캐시를 버린다 (테스트 격리용)."""
    _entries.clear()


# 테스트에서 이것만 바꿔 끼워 실제로 기다리지 않게 한다.
_sleep = asyncio.sleep


async def warm_up(tables: Mapping[str, Sequence[str]]) -> float:
    """부팅 때 표를 미리 읽고 인덱스까지 만들어 둔다. 읽는 데 걸린 시간(초, 기다린 시간 제외).

    재배치 직후엔 시트 복원이 파일을 방금 다시 써서 RACY_WINDOW_NS 규칙에 걸려 캐시에 남지 않는다.
    가장 늦게 바뀐 파일이 가라앉을 때까지 기다린 뒤 읽는다. 수정 시각이 미래여도 RACY_WINDOW_NS 까지만.
    """
    latest = max((os.stat(path).st_mtime_ns for path in tables), default=0)
    wait_ns = min(RACY_WINDOW_NS, RACY_WINDOW_NS - (time.time_ns() - latest))
    if wait_ns > 0:
        await _sleep(wait_ns / 1_000_000_000 + 0.05)

    started = time.monotonic()
    for path, columns in tables.items():
        table = read_table(path)
        for column in columns:
            table.index(column)
    return time.monotonic() - started
