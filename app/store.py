import asyncio
import csv
import os
import time
from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any
from gspread.exceptions import APIError

from app import table_cache
from app.client import (
    WRITING_PARTICIPATION_HEADER,
    SpreadSheetClient,
    is_quota_error,
)
from app.logging import log_event
from app.models import Bookmark

queue_lock = asyncio.Lock()

content_upload_queue: list[list[str]] = []
bookmark_upload_queue: list[list[str]] = []
bookmark_update_queue: list[Bookmark] = []  # TODO: 추후 타입 수정 필요
user_update_queue: list[list[str]] = []
coffee_chat_proof_upload_queue: list[list[str]] = []
point_history_upload_queue: list[list[str]] = []
paper_plane_upload_queue: list[list[str]] = []
subscription_upload_queue: list[list[str]] = []
subscription_update_queue: list[dict[str, Any]] = []
# writing_participation 은 기존 행을 갱신하는 테이블이라 행 단위 큐가 맞지 않는다.
# 변경 시 이 플래그만 켜고, upload_queue 가 clear + 전체 업로드로 시트에 반영한다.
writing_participation_dirty: bool = False

# 시트를 원본 백업으로 두는 테이블. restore_missing_tables / pull_all 의 대상.
SYNC_TABLES = [
    "users",
    "contents",
    "bookmark",
    "coffee_chat_proof",
    "point_histories",
    "paper_plane",
    "subscriptions",
    "writing_participation",
]

# 시트 API 한도(공식): 사용자당 읽기·쓰기 각 60/분, 배치 요청은 1건. 틱은 20초(분당 3회).
# 한 틱이 쓸 수 있는 요청 예산. 정상 최악 ≈ 9 (append 6 + 갱신 읽기1·쓰기1 + WP 1).
MAX_REQUESTS_PER_TICK = 20

# 429 백오프: 틱 단위. 1·2·4분 → 최대 5분. 틱 안에서 sleep 하지 않는다.
BACKOFF_BASE_SECONDS = 60
BACKOFF_MAX_SECONDS = 300
_backoff_until: float = 0.0
_backoff_level: int = 0


@dataclass
class FlushReport:
    """한 틱의 결과. 알림 정책(flush_alerts)의 입력."""

    requests: int = 0  # 이번 틱에 보낸 시트 API 요청 수
    skipped: list[str] = field(default_factory=list)  # 키를 못 찾아 버린 갱신 항목
    deferred: list[str] = field(default_factory=list)  # 예산 초과로 이월된 테이블
    backed_off: bool = False  # 백오프 창 안이라 아무것도 하지 않음


class SheetQuotaExceeded(Exception):
    """429. 큐는 보존됐고 retry_after 초 뒤 틱이 다시 시도한다."""

    def __init__(self, *, retry_after: float, level: int) -> None:
        super().__init__(
            f"시트 API 한도 초과(429) {level}회, {retry_after:.0f}초 백오프"
        )
        self.retry_after = retry_after
        self.level = level


def flush_alerts(
    report: FlushReport | None = None,
    error: Exception | None = None,
    prev_deferred: bool = False,
) -> list[str]:
    """틱 결과를 관리자 알림 문구로 바꾼다. 순수 함수.

    - 429 는 3회 이상 지속될 때만 (스팸 방지)
    - 못 찾아 버린 갱신은 데이터가 어긋났다는 신호라 항상
    - 이월은 시작될 때 1회 (edge-trigger)
    """
    alerts: list[str] = []
    if isinstance(error, SheetQuotaExceeded) and error.level >= 3:
        alerts.append(
            f"🫢 시트 API 한도 초과(429)가 {error.level}회 연속이에요. "
            f"{error.retry_after:.0f}초 뒤 다시 시도합니다. 큐는 보존됩니다."
        )
    if report is not None:
        if report.skipped:
            shown = ", ".join(report.skipped[:5])
            alerts.append(
                f"🫢 시트에서 갱신 대상을 못 찾아 건너뛴 항목 {len(report.skipped)}건: {shown}"
            )
        if report.deferred and not prev_deferred:
            alerts.append(
                "🫢 시트 요청 예산 초과로 이월된 테이블: "
                f"{', '.join(report.deferred)}. 계속되면 큐가 쌓입니다."
            )
    return alerts


def next_prev_deferred(report: FlushReport, prev: bool) -> bool:
    """이월 알림의 edge-trigger 상태. 백오프 틱은 아무것도 안 했으므로 상태를 건드리지 않는다."""
    if report.backed_off:
        return prev
    return bool(report.deferred)


def merge_writing_participation(
    local: list[list[str]], remote: list[list[str]]
) -> list[list[str]]:
    """로컬 ∪ 시트를 user_id 로 합친다. 로컬 순서·값 우선, 시트에만 있는 행은 뒤에.

    배포가 겹치는 구간에 옛 인스턴스가 늦게 올린 신청 행을 새 인스턴스의 통째 교체가
    지우지 않게 한다. 신청 행은 지워지는 일이 없으므로 합집합이 안전하다.
    시트의 짧은 행·빈 행은 버리고, 같은 user_id 는 처음 것만 쓴다.
    """
    header = (
        local[0] if local else (remote[0] if remote else WRITING_PARTICIPATION_HEADER)
    )
    width = len(header)
    merged = [header]
    seen: set[str] = set()
    for row in local[1:]:
        merged.append(row)
        if row:
            seen.add(row[0])
    for row in remote[1:]:
        if len(row) < width or not row[0] or row[0] in seen:
            continue
        seen.add(row[0])
        merged.append(row)
    return merged


# append 전용 큐: (테이블, 큐 이름, 로그 이벤트, 로그 타입, 라벨, 로그에 내용 포함 여부)
APPEND_SPECS = [
    (
        "contents",
        "content_upload_queue",
        "uploaded_contents",
        "content",
        "콘텐츠",
        True,
    ),
    (
        "bookmark",
        "bookmark_upload_queue",
        "uploaded_bookmarks",
        "content",
        "북마크",
        True,
    ),
    (
        "coffee_chat_proof",
        "coffee_chat_proof_upload_queue",
        "uploaded_coffee_chat_proofs",
        "community",
        "커피챗 인증",
        True,
    ),
    (
        "point_histories",
        "point_history_upload_queue",
        "uploaded_point_histories",
        "point",
        "포인트 내역",
        True,
    ),
    (
        "paper_plane",
        "paper_plane_upload_queue",
        "uploaded_paper_plane",
        "community",
        "종이비행기",
        False,
    ),
    (
        "subscriptions",
        "subscription_upload_queue",
        "uploaded_subscription",
        "subscription",
        "구독 내역",
        True,
    ),
]

# 갱신 큐: 항목의 키로 시트 행을 찾아 그 행을 덮어쓴다. 읽기는 키 컬럼만.
UPDATE_SPECS: dict[str, dict] = {
    "bookmark": dict(
        queue="bookmark_update_queue",
        key_range="bookmark!A2:C",
        key_of_row=lambda r: (r[0], r[2]) if len(r) > 2 else None,
        key_of_item=lambda b: (b.user_id, str(b.content_ts)),
        values_of=lambda b: b.to_list_for_sheet(),
        last_col="G",
        event=("updated_bookmarks", "content", "북마크 업데이트"),
    ),
    "subscriptions": dict(
        queue="subscription_update_queue",
        key_range="subscriptions!A2:A",
        key_of_row=lambda r: (r[0],) if r else None,
        key_of_item=lambda d: (str(d["id"]),),
        values_of=lambda d: list(d.values()),
        last_col="G",
        event=("updated_subscriptions", "subscription", "구독 내역 업데이트"),
    ),
    "users": dict(
        queue="user_update_queue",
        key_range="users!A2:A",
        key_of_row=lambda r: (r[0],) if r else None,
        key_of_item=lambda v: (v[0],),
        values_of=lambda v: v,
        last_col="F",
        event=("updated_user_introduction", "user", "유저 자기소개 업데이트"),
    ),
}
UPDATE_ORDER = ["bookmark", "subscriptions", "users"]


def _drain(queue: list) -> tuple[list, int]:
    """지금 있는 만큼만 복사해 온다. 업로드 중 append 된 항목은 다음 틱으로 남는다."""
    n = len(queue)
    return list(queue[:n]), n


def _commit(queue: list, n: int) -> None:
    """업로드에 성공한 개수만큼 앞에서 지운다. 값 비교가 아니라 개수라 동일값도 안전."""
    del queue[:n]


class Store:
    def __init__(self, client: SpreadSheetClient) -> None:
        self._client = client

    def pull_all(self) -> None:
        """데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("users", values=self._client.get_values("users"))
        self.write("contents", values=self._client.get_values("contents"))
        self.write("bookmark", values=self._client.get_values("bookmark"))
        self.write(
            "coffee_chat_proof", values=self._client.get_values("coffee_chat_proof")
        )
        self.write("point_histories", values=self._client.get_values("point_histories"))
        self.write("paper_plane", values=self._client.get_values("paper_plane"))
        self.write("subscriptions", values=self._client.get_values("subscriptions"))
        self.write(
            "writing_participation",
            values=self._client.get_values("writing_participation"),
        )

    def pull_users(self) -> None:
        """유저 데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("users", values=self._client.get_values("users"))

    def pull_contents(self) -> None:
        """콘텐츠 데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("contents", values=self._client.get_values("contents"))

    def pull_bookmark(self) -> None:
        """북마크 데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("bookmark", values=self._client.get_values("bookmark"))

    def pull_coffee_chat_proof(self) -> None:
        """커피챗 인증 데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write(
            "coffee_chat_proof", values=self._client.get_values("coffee_chat_proof")
        )

    def pull_point_histories(self) -> None:
        """포인트 내역 데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("point_histories", values=self._client.get_values("point_histories"))

    def pull_paper_plane(self) -> None:
        """종이비행기 데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("paper_plane", values=self._client.get_values("paper_plane"))

    def pull_subscriptions(self) -> None:
        """구독 내역 데이터를 가져와 서버 저장소를 동기화합니다."""
        os.makedirs("store", exist_ok=True)
        self.write("subscriptions", values=self._client.get_values("subscriptions"))

    def pull_writing_participation(self) -> None:
        """글쓰기 참여 신청 데이터를 가져와 서버 저장소를 동기화합니다.

        탭이 완전히 비어 있으면 0바이트 대신 헤더 1행을 쓴다 (pandas EmptyDataError 방지).
        """
        os.makedirs("store", exist_ok=True)
        values = self._client.get_values("writing_participation") or [
            WRITING_PARTICIPATION_HEADER
        ]
        self.write("writing_participation", values=values)

    def _merge_wp_locally(self, remote: list[list[str]]) -> list[list[str]]:
        """로컬 CSV 와 시트를 합쳐 로컬에 되쓰고 합친 표를 돌려준다. 파일 IO 는 이벤트 루프에서.

        핸들러의 to_csv 도 루프에서 실행되므로 스레드에서 읽을 때 생기는 찢긴 읽기가 없다.
        """
        try:
            local = self.read("writing_participation")
        except FileNotFoundError:
            local = []
        merged = merge_writing_participation(local, remote)
        if merged != local:
            os.makedirs("store", exist_ok=True)
            self.write("writing_participation", merged)
        return merged

    def upload_writing_participation(self) -> None:
        """글쓰기 참여 신청 테이블을 시트에 반영합니다 (읽기 1 + resize 1 + update 1).

        기존 행을 갱신하는 테이블이라 append 전용 bulk_upload 만으로는 중복이 생긴다.
        시트와 합집합을 만든 뒤 통째로 바꾸므로, 배포 겹침 구간에 옛 인스턴스가 늦게 올린
        행도 지워지지 않는다.
        """
        remote = self._client.get_values("writing_participation")
        merged = self._merge_wp_locally(remote)
        self._client.replace_table("writing_participation", merged)

    @staticmethod
    def _needs_restore(table_name: str) -> bool:
        path = f"store/{table_name}.csv"
        return not os.path.exists(path) or os.path.getsize(path) == 0

    def restore_missing_tables(self) -> list[str]:
        """로컬 CSV 가 없거나 0바이트인 테이블만 시트에서 복원하고, 복원한 이름을 돌려줍니다.

        로컬이 원본(시트보다 최대 20초 앞섬)이므로 파일이 있으면 절대 덮어쓰지 않는다.
        무조건 pull_all 은 디스크 유지 서버에서 최근 쓰기를 되감아 유실을 만든다.
        Koyeb 처럼 재배치마다 디스크가 초기화되는 환경에서 자동 복원용으로 쓴다.
        """
        pullers = {
            "users": self.pull_users,
            "contents": self.pull_contents,
            "bookmark": self.pull_bookmark,
            "coffee_chat_proof": self.pull_coffee_chat_proof,
            "point_histories": self.pull_point_histories,
            "paper_plane": self.pull_paper_plane,
            "subscriptions": self.pull_subscriptions,
            "writing_participation": self.pull_writing_participation,
        }
        restored: list[str] = []
        for table_name in SYNC_TABLES:
            if self._needs_restore(table_name):
                pullers[table_name]()
                restored.append(table_name)
        return restored

    def write(self, table_name: str, values: list[list[str]]) -> None:
        """데이터를 저장소에 저장합니다."""
        with open(f"store/{table_name}.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerows(values)
        # 통째로 다시 썼으니 표 캐시를 버린다 (시트 복원·관리자 동기화, worklog 023).
        table_cache.invalidate(f"store/{table_name}.csv")

    def read(self, table_name: str) -> list[list[str]]:
        """저장소에서 데이터를 읽어옵니다."""
        with open(f"store/{table_name}.csv") as f:
            reader = csv.reader(f, quoting=csv.QUOTE_ALL)
            data = list(reader)
        return data

    def upload_all(self, table_name: str) -> None:
        """해당 테이블의 모든 데이터를 업로드합니다."""
        values = self.read(table_name)
        self._client.bulk_upload(table_name, values)

    async def upload_queue(
        self,
        *,
        force: bool = False,
        now: Callable[[], float] = time.monotonic,
    ) -> FlushReport:
        """큐를 시트에 반영합니다. 틱당 요청 예산 안에서, 429 는 틱 단위로 백오프합니다.

        - append 큐 → 테이블당 쓰기 1
        - 갱신 3테이블 → 읽기 1(키 컬럼만) + 쓰기 1(values.batchUpdate)
        - writing_participation → 쓰기 1(replace_table)
        - force: shutdown 의 마지막 flush 처럼 백오프를 무시하고 한 번 시도할 때
        """
        global _backoff_until, _backoff_level
        global writing_participation_dirty

        report = FlushReport()
        if not force and now() < _backoff_until:
            report.backed_off = True
            return report

        async with queue_lock:
            budget = MAX_REQUESTS_PER_TICK

            # 어떤 await 도 하기 전에 모든 큐를 스냅샷한다. 핸들러는 생성 → 갱신 순으로 동기적으로
            # enqueue 하므로, 스냅샷에 갱신이 있으면 그 행의 생성도 스냅샷에 있거나 이미 시트에 있다.
            # (틱 도중 들어온 "생성 + 즉시 취소" 가 갱신만 먼저 처리돼 버려지는 일을 막는다)
            append_snap = [
                (spec, globals()[spec[1]], *_drain(globals()[spec[1]]))
                for spec in APPEND_SPECS
                if globals()[spec[1]]
            ]
            update_snap = [
                (
                    table,
                    globals()[UPDATE_SPECS[table]["queue"]],
                    *_drain(globals()[UPDATE_SPECS[table]["queue"]]),
                )
                for table in UPDATE_ORDER
                if globals()[UPDATE_SPECS[table]["queue"]]
            ]
            wp_dirty = writing_participation_dirty
            writing_participation_dirty = False  # 틱 중 새 쓰기는 플래그를 다시 켠다

            try:
                # 1) append 전용 큐
                for (
                    (table, _qn, event, type_, label, keep_body),
                    queue,
                    batch,
                    n,
                ) in append_snap:
                    cost = max(1, -(-n // 1000))  # bulk_upload 는 1000행 단위 요청
                    if cost > budget:
                        report.deferred.append(table)
                        continue
                    await asyncio.to_thread(self._client.bulk_upload, table, batch)
                    _commit(queue, n)
                    budget -= cost
                    report.requests += cost
                    log_event(
                        actor="system",
                        event=event,
                        type=type_,
                        description=f"{n}개 {label} 업로드",
                        body={"uploaded": batch} if keep_body else {},
                    )

                # 2) 갱신 큐: 읽기 1 + 쓰기 1
                if update_snap:
                    if budget < 2:
                        report.deferred.extend(table for table, *_ in update_snap)
                    else:
                        ranges = [
                            UPDATE_SPECS[table]["key_range"]
                            for table, *_ in update_snap
                        ]
                        sheet_rows = await asyncio.to_thread(
                            self._client.batch_get, ranges
                        )
                        budget -= 1
                        report.requests += 1

                        data: list[dict] = []
                        # 응답이 요청보다 적으면 조용히 이월하지 않고 실패시킨다 (strict)
                        for (table, queue, batch, n), rows in zip(
                            update_snap, sheet_rows, strict=True
                        ):
                            spec = UPDATE_SPECS[table]
                            index: dict = {}
                            for i, row in enumerate(rows):
                                key = spec["key_of_row"](row)
                                if key is not None:
                                    index.setdefault(key, []).append(
                                        i + 2
                                    )  # 1행 헤더, i 는 0부터
                            last: dict = {}
                            for item in batch:
                                last[spec["key_of_item"](item)] = (
                                    item  # 같은 행은 마지막 값
                                )
                            for key, item in last.items():
                                row_numbers = index.get(key)
                                if not row_numbers:
                                    # 못 찾으면 어떤 행도 쓰지 않는다. (기존: 2행을 덮어쓰는 버그)
                                    report.skipped.append(
                                        f"{table}:{key[0] if len(key) == 1 else key}"
                                    )
                                    continue
                                # 같은 키 행이 여럿이면(재북마크) 전부 같은 값으로. 로컬 동작과 일치.
                                for row_number in row_numbers:
                                    data.append(
                                        {
                                            "range": f"{table}!A{row_number}:{spec['last_col']}{row_number}",
                                            "values": [spec["values_of"](item)],
                                        }
                                    )
                        if data:
                            await asyncio.to_thread(self._client.batch_update, data)
                            budget -= 1
                            report.requests += 1
                        for table, queue, batch, n in update_snap:
                            _commit(queue, n)
                            event, type_, label = UPDATE_SPECS[table]["event"]
                            log_event(
                                actor="system",
                                event=event,
                                type=type_,
                                description=f"{len(batch)}개 {label}",
                                body={},
                            )

                # 3) writing_participation: 읽기 1(병합용) + resize 1 + update 1
                if wp_dirty:
                    if budget < 3:
                        report.deferred.append("writing_participation")
                        writing_participation_dirty = True
                    else:
                        try:
                            remote = await asyncio.to_thread(
                                self._client.get_values, "writing_participation"
                            )
                            merged = self._merge_wp_locally(
                                remote
                            )  # 파일 IO 는 루프에서
                            await asyncio.to_thread(
                                self._client.replace_table,
                                "writing_participation",
                                merged,
                            )
                        except Exception:
                            writing_participation_dirty = True
                            raise
                        budget -= 3
                        report.requests += 3
                        log_event(
                            actor="system",
                            event="uploaded_writing_participation",
                            type="system",
                            description="글쓰기 참여 신청 전체 반영",
                            body={},
                        )
            except APIError as e:
                if is_quota_error(e):
                    _backoff_level += 1
                    retry_after = min(
                        BACKOFF_BASE_SECONDS * 2 ** (_backoff_level - 1),
                        BACKOFF_MAX_SECONDS,
                    )
                    _backoff_until = now() + retry_after
                    raise SheetQuotaExceeded(
                        retry_after=retry_after, level=_backoff_level
                    ) from e
                raise

        _backoff_level = 0
        _backoff_until = 0.0  # force 로 창 안에서 성공한 뒤에도 다음 틱이 건너뛰지 않게
        return report

    def backup(self, table_name: str) -> None:
        values = self.read(table_name)
        self._client.backup(values)

    def initialize_logs(self) -> None:
        """로그를 초기화합니다."""
        open("store/logs.csv", "w").close()
