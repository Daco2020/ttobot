"""테스트 전역 픽스처.

- `slack_repo`, `point_service`, `background_service` : 기존 서비스 픽스처
- `slack_app` : 가벼운 fake 슬랙 앱 (chat_postMessage 호출만 받음)
- `fake_slack_client` : 모든 메서드를 `AsyncMock`으로 갖는 가짜 슬랙 클라이언트
- `tmp_store` : `store/` 하위 빈 CSV들을 임시 디렉터리에 헤더만 작성하고 cwd를 옮김
- `factory` : 모델 팩토리 모듈 그대로 노출 (사용 시 `factory.make_user(...)`)
"""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# app.client 의 SpreadSheetClient 는 default argument 로 gc.open_by_url(...) 을 호출한다.
# 즉 app 을 import 만 해도 import 시점에 Google Sheets 네트워크 호출이 일어난다.
# 테스트는 외부 의존성을 모두 mock 하므로, gspread 도 import 전에 mock 으로 차단해서
# CI 환경(더미 크리덴셜) 에서도 안전하게 import 되도록 한다.
import gspread

gspread.authorize = MagicMock(return_value=MagicMock())  # type: ignore[assignment]

from app.slack.repositories import SlackRepository  # noqa: E402
from app.slack.services.background import BackgroundService  # noqa: E402
from app.slack.services.point import PointService  # noqa: E402

from test import factories  # noqa: E402


@pytest.fixture
def factory():
    return factories


@pytest.fixture
def slack_repo() -> SlackRepository:
    return SlackRepository()


@pytest.fixture
def background_service(slack_repo: SlackRepository) -> BackgroundService:
    return BackgroundService(slack_repo)


@pytest.fixture
def point_service(slack_repo: SlackRepository) -> PointService:
    return PointService(slack_repo)


class FakeAsyncWebClient:
    """매우 단순한 fake. 메서드 호출 자체는 noop이고, 검증이 필요하면 patch.object로 감싼다.

    각 슬랙 SDK 메서드는 noop 으로 정의해두어 mypy 의 attr-defined 에러를 막는다.
    필요하면 테스트에서 `mocker.patch.object(client, "메서드명", new=AsyncMock(...))` 로 갈아끼운다.
    """

    def __init__(self) -> None: ...

    async def chat_postMessage(self, **kwargs) -> None: ...

    async def chat_getPermalink(self, **kwargs) -> dict: ...  # type: ignore[empty-body]


class FakeSlackApp:
    def __init__(self) -> None:
        self._async_client = FakeAsyncWebClient()

    @property
    def client(self) -> FakeAsyncWebClient:
        return self._async_client


@pytest.fixture
def slack_app() -> FakeSlackApp:
    return FakeSlackApp()


@pytest.fixture
def fake_slack_client() -> AsyncMock:
    """슬랙 클라이언트의 모든 호출을 받아주는 AsyncMock.

    개별 메서드의 응답값은 테스트에서 `client.conversations_history.return_value = {...}` 식으로 지정한다.
    """
    client = AsyncMock()
    # views_open/update/publish 같은 메서드도 자동으로 AsyncMock이 됨
    return client


# ---------------------------------------------------------------------------
# CSV 격리
# ---------------------------------------------------------------------------

# 헤더만 미리 깔아둘 CSV 파일들 (실제 컬럼은 모델 fieldnames와 맞춰서 정의).
_STORE_FILES: dict[str, list[str]] = {
    "users.csv": [
        "user_id",
        "name",
        "channel_name",
        "channel_id",
        "intro",
        "deposit",
        "cohort",
    ],
    "contents.csv": [
        "user_id",
        "username",
        "title",
        "content_url",
        "dt",
        "category",
        "description",
        "type",
        "tags",
        "curation_flag",
        "ts",
        "feedback_intensity",
    ],
    "bookmark.csv": [
        "user_id",
        "content_user_id",
        "content_ts",
        "note",
        "status",
        "created_at",
        "updated_at",
    ],
    "coffee_chat_proof.csv": [
        "ts",
        "thread_ts",
        "user_id",
        "text",
        "image_urls",
        "selected_user_ids",
        "participant_call_thread_ts",
        "created_at",
    ],
    "point_histories.csv": [
        "id",
        "user_id",
        "reason",
        "point",
        "category",
        "created_at",
    ],
    "paper_plane.csv": [
        "id",
        "sender_id",
        "sender_name",
        "receiver_id",
        "receiver_name",
        "text",
        "text_color",
        "bg_color",
        "color_label",
        "created_at",
    ],
    "subscriptions.csv": [
        "id",
        "user_id",
        "target_user_id",
        "target_user_channel",
        "status",
        "created_at",
        "updated_at",
    ],
    "writing_participation.csv": [
        "user_id",
        "name",
        "created_at",
        "is_writing_participation",
    ],
    "_inflearn_coupon.csv": ["code", "expired_at"],
    "_checked_notice.csv": ["user_id", "notice_ts", "created_at"],
    "_checked_super_admin_post.csv": ["user_id", "post_id", "channel_id", "created_at"],
}


@pytest.fixture(autouse=True, scope="session")
def _ensure_store_csv_skeleton() -> None:
    """`tmp_store` 픽스처를 쓰지 않는 테스트들이 `User.is_writing_participation` 같은 property 를
    통해 진짜 `store/*.csv` 를 읽어들일 때, CI 환경처럼 store/ 가 비어 있어도 동작하도록
    헤더만 있는 빈 CSV 를 미리 깔아둔다.

    - 이미 파일이 존재하면 건드리지 않는다 (로컬 운영 데이터 보호).
    - autouse + scope="session" 으로 세션당 1회만 실행.
    """
    store_dir = Path("store")
    store_dir.mkdir(exist_ok=True)
    for name, header in _STORE_FILES.items():
        path = store_dir / name
        if path.exists():
            continue
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(header)


@pytest.fixture
def tmp_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """임시 store 디렉터리를 만들고 cwd를 그쪽으로 옮긴다.

    각 CSV는 헤더만 들어있는 빈 파일로 초기화. 테스트에서 행을 추가하고 싶다면
    `tmp_store / "users.csv"`에 직접 쓰거나 `write_csv_rows` 헬퍼를 활용한다.
    """
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    for name, header in _STORE_FILES.items():
        path = store_dir / name
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(header)
    monkeypatch.chdir(tmp_path)
    return store_dir


def write_csv_rows(path: Path, header: list[str], rows: list[dict]) -> None:
    """헤더 + dict 행들을 CSV로 쓴다 (덮어쓰기)."""
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


@pytest.fixture
def csv_writer_helper():
    """편의를 위해 helper 함수를 그대로 노출."""
    return write_csv_rows
