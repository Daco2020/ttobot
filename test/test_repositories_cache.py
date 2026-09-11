"""SlackRepository 의 users·contents·point_histories 읽기를 table_cache 로 (worklog 023).

가설
- 조회 결과가 옛 구현(요청마다 csv.DictReader)과 같다. 캐시 적중 뒤에도 같다.
- 파일이 그대로면 요청이 여러 번 와도 표마다 한 번만 파싱한다.
- 받은 모델·목록을 고쳐도 다음 조회에 번지지 않는다 (SlackService 가 contents 에 append 한다).
- 쓰기 → 읽기 round-trip: 글 추가(update)·포인트 추가(add_point)는 다시 파싱 없이 바로 보이고,
  자기소개 재작성(update_user_intro)·시트 복원 같은 통째 재작성도 바로 보인다.
"""

from __future__ import annotations

import csv
import os
import time
from pathlib import Path
from typing import Any, Callable

import pytest
from pydantic import BaseModel
from pytest_mock import MockerFixture

from app import models
from app import store as store_module
from app import table_cache
from app.slack.repositories import SlackRepository
from test import factories

USERS_HEADER = [
    "user_id",
    "name",
    "channel_name",
    "channel_id",
    "intro",
    "deposit",
    "cohort",
]


@pytest.fixture(autouse=True)
def _isolate_queues_and_cache():
    table_cache.clear()
    store_module.content_upload_queue = []
    store_module.user_update_queue = []
    yield
    store_module.content_upload_queue = []
    store_module.user_update_queue = []
    table_cache.clear()


def _age(path: Path, seconds: int = 60) -> None:
    ns = time.time_ns() - seconds * 1_000_000_000
    os.utime(path, ns=(ns, ns))


def _user_row(**overrides: str) -> dict[str, str]:
    row = {
        "user_id": "U1",
        "name": "김철수",
        "channel_name": "1_백엔드",
        "channel_id": "C1",
        "intro": "안녕",
        "deposit": "100000",
        "cohort": "10기",
    }
    row.update(overrides)
    return row


def _content_row(**overrides: str) -> dict[str, str]:
    row = {
        "user_id": "U1",
        "username": "김철수",
        "title": "글",
        "content_url": "https://e.com/x",
        "dt": "2026-09-01 10:00:00",
        "category": "기술 & 언어",
        "description": "",
        "type": "submit",
        "tags": "",
        "curation_flag": "N",
        "ts": "0.0",
        "feedback_intensity": "HOT",
    }
    row.update(overrides)
    return row


def _point_row(**overrides: str) -> dict[str, str]:
    row = {
        "id": "p0",
        "user_id": "U1",
        "reason": "글 제출",
        "point": "100",
        "category": "글쓰기",
        "created_at": "2026-09-01 10:00:00",
    }
    row.update(overrides)
    return row


@pytest.fixture
def seeded_store(tmp_store: Path, csv_writer_helper) -> Path:
    csv_writer_helper(
        tmp_store / "users.csv",
        USERS_HEADER,
        [
            _user_row(),
            _user_row(user_id="U2", name="김철", channel_id="C2", intro="", deposit=""),
            _user_row(user_id="U3", name="이영희", channel_id="C3", cohort="9기"),
        ],
    )
    csv_writer_helper(
        tmp_store / "contents.csv",
        models.Content.fieldnames(),
        [
            _content_row(
                dt="2026-08-31 10:00:00",
                ts="1.0",
                title="파이썬 캐시",
                content_url="https://e.com/1",
            ),
            _content_row(
                user_id="U2",
                username="김철",
                dt="2026-08-30 10:00:00",
                ts="2.0",
                title="리액트",
                tags="react",
                content_url="https://e.com/2",
            ),
            _content_row(
                dt="2026-08-29 10:00:00",
                ts="3.0",
                type="pass",
                title="",
                content_url="",
            ),
            _content_row(
                dt="2026-09-10 10:00:00",
                ts="4.0",
                title="Koyeb 이전기",
                description="캐시 이야기",
                content_url="https://e.com/4",
            ),
        ],
    )
    csv_writer_helper(
        tmp_store / "point_histories.csv",
        models.PointHistory.fieldnames(),
        [
            _point_row(id="p1", created_at="2026-09-01 10:00:00"),
            _point_row(id="p2", user_id="U2", created_at="2026-09-02 10:00:00"),
            _point_row(id="p3", point="50", created_at="2026-09-03 10:00:00"),
        ],
    )
    for name in ("users.csv", "contents.csv", "point_histories.csv"):
        _age(tmp_store / name)
    return tmp_store


class LegacyReads:
    """worklog 023 이전 SlackRepository 조회 코드 그대로 (매번 csv.DictReader). 동등성 비교 기준."""

    def _fetch_users(self) -> list[dict[str, Any]]:
        with open("store/users.csv") as f:
            return [dict(row) for row in csv.DictReader(f)]

    def _get_user(self, user_id: str) -> models.User | None:
        for user in self._fetch_users():
            if user["user_id"] == user_id:
                return models.User(**user)
        return None

    def _fetch_contents(self, user_id: str) -> list[models.Content]:
        with open("store/contents.csv") as f:
            return [
                models.Content(**c)
                for c in csv.DictReader(f)
                if c["user_id"] == user_id
            ]

    def get_user(self, user_id: str) -> models.User | None:
        if user := self._get_user(user_id):
            user.contents = self._fetch_contents(user_id)
            return user
        return None

    def get_only_user(self, user_id: str) -> models.User | None:
        return self._get_user(user_id)

    def fetch_users(self) -> list[models.User]:
        users = [models.User(**user) for user in self._fetch_users()]
        for user in users:
            user.contents = self._fetch_contents(user.user_id)
        return users

    def fetch_contents(self) -> list[models.Content]:
        with open("store/contents.csv") as f:
            contents = [
                models.Content(**c) for c in csv.DictReader(f) if c["type"] == "submit"
            ]
        return sorted(contents, key=lambda c: c.dt_, reverse=True)

    def fetch_contents_by_keyword(self, keyword: str) -> list[models.Content]:
        with open("store/contents.csv") as f:
            contents = [
                models.Content(**c)
                for c in csv.DictReader(f)
                if keyword.lower()
                in (c["title"] + c["description"] + c["tags"]).lower()
                and c["type"] == "submit"
            ]
        return sorted(contents, key=lambda c: c.dt_, reverse=True)

    def get_user_id_by_name(self, name: str) -> str | None:
        with open("store/users.csv") as f:
            matching = [u for u in csv.DictReader(f) if name in u["name"]]
        if len(matching) == 1:
            return matching[0]["user_id"]
        elif len(matching) > 1:
            for u in matching:
                if u["name"] == name:
                    return u["user_id"]
        return None

    def fetch_user_ids_by_name(self, name: str) -> list[str]:
        with open("store/users.csv") as f:
            return [u["user_id"] for u in csv.DictReader(f) if name in u["name"]]

    def get_content_by(
        self,
        ts: str | None = None,
        user_id: str | None = None,
        dt: str | None = None,
        content_url: str | None = None,
    ) -> models.Content | None:
        with open("store/contents.csv") as f:
            contents = [
                models.Content(**c)
                for c in csv.DictReader(f)
                if c["ts"] == ts
                or (c["user_id"] == user_id and c["dt"] == dt)
                or (c["content_url"] == content_url)
            ]
        if not contents:
            return None
        return sorted(contents, key=lambda c: c.dt_, reverse=True)[0]

    def has_point_history_id(self, history_id: str) -> bool:
        with open("store/point_histories.csv") as f:
            return any(row["id"] == history_id for row in csv.DictReader(f))

    def fetch_point_histories(self, user_id: str) -> list[models.PointHistory]:
        with open("store/point_histories.csv") as f:
            histories = [
                models.PointHistory(**p)
                for p in csv.DictReader(f)
                if p["user_id"] == user_id
            ]
        return sorted(histories, key=lambda p: p.created_at, reverse=True)


def _dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, list):
        return [_dump(v) for v in value]
    return value


READ_CALLS: dict[str, Callable[[Any], Any]] = {
    "get_user": lambda r: r.get_user("U1"),
    "get_user_없음": lambda r: r.get_user("U404"),
    "get_only_user": lambda r: r.get_only_user("U2"),
    "_fetch_users": lambda r: r._fetch_users(),
    "fetch_users": lambda r: r.fetch_users(),
    "fetch_contents": lambda r: r.fetch_contents(),
    "keyword_한글": lambda r: r.fetch_contents_by_keyword("캐시"),
    "keyword_대소문자": lambda r: r.fetch_contents_by_keyword("REACT"),
    "content_by_ts": lambda r: r.get_content_by(ts="3.0"),
    "content_by_user_dt": lambda r: r.get_content_by(
        user_id="U1", dt="2026-08-31 10:00:00"
    ),
    "content_by_빈_url": lambda r: r.get_content_by(content_url=""),
    "content_by_조건없음": lambda r: r.get_content_by(),
    "id_by_name_정확히": lambda r: r.get_user_id_by_name("김철"),
    "id_by_name_여럿": lambda r: r.get_user_id_by_name("김"),
    "id_by_name_하나": lambda r: r.get_user_id_by_name("영희"),
    "ids_by_name": lambda r: r.fetch_user_ids_by_name("김"),
    "has_point_id": lambda r: r.has_point_history_id("p3"),
    "has_point_id_없음": lambda r: r.has_point_history_id("p404"),
    "point_histories": lambda r: r.fetch_point_histories("U1"),
    "point_histories_없음": lambda r: r.fetch_point_histories("U404"),
}


@pytest.mark.parametrize("name", list(READ_CALLS))
def test_reads_match_legacy_implementation(seeded_store: Path, name: str) -> None:
    """✅ 조회 결과가 옛 구현과 같다. 같은 저장소로 두 번 불러 캐시 적중 뒤 결과도 비교한다."""
    call = READ_CALLS[name]
    expected = _dump(call(LegacyReads()))
    repo = SlackRepository()

    assert _dump(call(repo)) == expected
    assert _dump(call(repo)) == expected


def test_repeated_requests_parse_each_table_once(
    seeded_store: Path, mocker: MockerFixture
) -> None:
    """✅ 홈 탭(미들웨어 get_user + 포인트 조회)이 세 번 와도 표마다 한 번만 파싱한다."""
    parse = mocker.spy(table_cache, "_parse")

    for _ in range(3):
        repo = SlackRepository()
        repo.get_user("U1")
        repo.fetch_point_histories("U1")

    parsed = sorted(Path(c.args[0]).name for c in parse.call_args_list)
    assert parsed == ["contents.csv", "point_histories.csv", "users.csv"]


def test_mutating_returned_models_does_not_leak(seeded_store: Path) -> None:
    """⚠️ SlackService 처럼 받은 contents 목록에 append 하거나 모델을 고쳐도 다음 조회는 그대로다."""
    repo = SlackRepository()
    user = repo.get_user("U1")
    assert user is not None
    user.contents.append(factories.make_content(user_id="U1", ts="999.0"))
    user.name = "바뀐 이름"
    repo.fetch_point_histories("U1").clear()

    again = repo.get_user("U1")

    assert again is not None
    assert "999.0" not in [c.ts for c in again.contents]
    assert again.name == "김철수"
    assert len(repo.fetch_point_histories("U1")) == 2


def test_update_appends_content_visible_without_reparse(
    seeded_store: Path, mocker: MockerFixture
) -> None:
    """결합: 글 추가(update) → 다음 조회에 바로 보이고 contents 를 다시 파싱하지 않는다. 디스크도 같다."""
    repo = SlackRepository()
    user = repo.get_user("U1")
    assert user is not None
    parse = mocker.spy(table_cache, "_parse")
    user.contents.append(
        factories.make_content(
            user_id="U1",
            username="김철수",
            ts="5.0",
            dt="2026-09-11 22:00:00",
            title="새 글",
            content_url="https://e.com/5",
        )
    )

    repo.update(user)

    again = repo.get_user("U1")
    assert again is not None
    assert again.contents[-1].ts == "5.0"
    content = repo.get_content_by(ts="5.0")
    assert content is not None and content.title == "새 글"
    assert "contents.csv" not in [Path(c.args[0]).name for c in parse.call_args_list]
    assert _dump(repo.fetch_contents()) == _dump(LegacyReads().fetch_contents())


def test_add_point_visible_to_fetch_and_dedup_check(
    seeded_store: Path, mocker: MockerFixture
) -> None:
    """결합: 포인트 추가 → 내역 조회·중복 판정에 바로 보이고 다시 파싱하지 않는다."""
    repo = SlackRepository()
    repo.fetch_point_histories("U1")
    parse = mocker.spy(table_cache, "_parse")

    repo.add_point(
        factories.make_point_history(
            id="notice:U1:1.0",
            user_id="U1",
            reason="공지사항 확인",
            point=20,
            created_at="2026-09-30 10:00:00",
        )
    )

    assert repo.has_point_history_id("notice:U1:1.0") is True
    assert repo.fetch_point_histories("U1")[0].id == "notice:U1:1.0"
    assert parse.call_count == 0
    assert _dump(repo.fetch_point_histories("U1")) == _dump(
        LegacyReads().fetch_point_histories("U1")
    )


def test_update_user_intro_invalidates_even_if_file_key_looks_same(
    seeded_store: Path, mocker: MockerFixture
) -> None:
    """⚠️ 재작성 뒤 파일 상태 키(inode·크기·수정 시각)가 우연히 같아도, 시트로 올라갈 값과
    다음 조회는 새 자기소개다. 앱 안 재작성은 캐시를 직접 버린다."""
    repo = SlackRepository()
    mocker.patch.object(table_cache, "_key_of", return_value=(1, 1, 1))
    user = repo.get_user("U1")
    assert user is not None and user.intro == "안녕"

    repo.update_user_intro("U1", "잘가")

    assert store_module.user_update_queue[-1][4] == "잘가"
    again = repo.get_user("U1")
    assert again is not None and again.intro == "잘가"


def test_external_rewrite_like_sheet_restore_is_visible(
    seeded_store: Path, csv_writer_helper
) -> None:
    """결합: 시트 복원(pull_*)처럼 밖에서 표를 통째로 다시 쓰면 다음 조회에 보인다."""
    repo = SlackRepository()
    assert len(repo.fetch_point_histories("U1")) == 2

    csv_writer_helper(
        seeded_store / "point_histories.csv",
        models.PointHistory.fieldnames(),
        [_point_row(id="p9")],
    )

    assert [h.id for h in repo.fetch_point_histories("U1")] == ["p9"]


@pytest.mark.asyncio
async def test_warm_up_covers_hot_repository_reads(
    seeded_store: Path, mocker: MockerFixture
) -> None:
    """결합: 부팅 워밍업(SlackRepository.warm_up) 뒤에는 미들웨어·홈 탭·포인트 내역·공지 중복 판정이
    파싱 없이 돈다. 재시작 직후 첫 요청이 3초(trigger)를 넘기지 않게 하려는 것."""
    await SlackRepository.warm_up()
    parse = mocker.spy(table_cache, "_parse")
    repo = SlackRepository()

    user = repo.get_user("U1")
    assert user is not None
    repo.fetch_point_histories("U1")
    repo.has_point_history_id("p1")

    assert parse.call_count == 0
    point_indexes = table_cache.read_table("store/point_histories.csv")._indexes
    assert {"user_id", "id"} <= set(point_indexes)


def test_store_write_invalidates_even_if_file_key_looks_same(
    seeded_store: Path, mocker: MockerFixture
) -> None:
    """⚠️ 시트 복원·관리자 동기화(Store.write)로 표를 통째로 다시 쓰면, 파일 상태 키가 우연히 같아도
    다음 조회는 새 내용이다. 앱 안 재작성은 캐시를 직접 버린다."""
    repo = SlackRepository()
    mocker.patch.object(table_cache, "_key_of", return_value=(1, 1, 1))
    assert len(repo.fetch_point_histories("U1")) == 2

    store_module.Store(client=mocker.MagicMock()).write(
        "point_histories",
        [models.PointHistory.fieldnames(), list(_point_row(id="p9").values())],
    )

    assert [h.id for h in repo.fetch_point_histories("U1")] == ["p9"]
