"""슬랙 writing_participation 이벤트 핸들러 테스트.

대상: app/slack/events/writing_participation.py
- open_writing_participation_view (신청 / 완료 안내)
- submit_writing_participation_view (CSV 신규/기존 갱신, DM 메시지)
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import pytest

from app.slack.events import writing_participation as wp_events
from test.slack.conftest import make_action_body, make_view_body


WP_HEADER = ["user_id", "name", "created_at", "is_writing_participation"]


def _read_wp_csv(path: Path) -> list[dict[str, str]]:
    with path.open() as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


# ---------------------------------------------------------------------------
# open_writing_participation_view
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_view_when_already_participating_shows_complete_modal(
    ack, fake_slack_client, factory, mocker
) -> None:
    """✅ 이미 신청한 유저 → 완료 안내 모달."""
    user = factory.make_user(user_id="U_X")
    mocker.patch.object(
        type(user), "is_writing_participation", new_callable=mocker.PropertyMock
    ).return_value = True

    await wp_events.open_writing_participation_view(
        ack=ack,
        body=make_action_body(),
        client=fake_slack_client,
        user=user,
    )

    fake_slack_client.views_open.assert_awaited_once()
    view = fake_slack_client.views_open.await_args.kwargs["view"]
    rendered = view.to_dict()
    body_text = "".join(
        b.get("text", {}).get("text", "")
        for b in rendered["blocks"]
        if b.get("text")
    )
    assert "이미 글쓰기 참여 신청을 완료했어요" in body_text
    # callback_id 가 없어야 한다 (제출 모달이 아니라 단순 안내)
    assert view.callback_id is None


@pytest.mark.asyncio
async def test_open_view_when_not_participating_shows_application_form(
    ack, fake_slack_client, factory, mocker
) -> None:
    """✅ 미신청 유저 → 신청 모달 (callback_id=writing_participation_view)."""
    user = factory.make_user(user_id="U_X")
    mocker.patch.object(
        type(user), "is_writing_participation", new_callable=mocker.PropertyMock
    ).return_value = False

    await wp_events.open_writing_participation_view(
        ack=ack,
        body=make_action_body(),
        client=fake_slack_client,
        user=user,
    )

    fake_slack_client.views_open.assert_awaited_once()
    view = fake_slack_client.views_open.await_args.kwargs["view"]
    assert view.callback_id == "writing_participation_view"


# ---------------------------------------------------------------------------
# submit_writing_participation_view
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_creates_csv_when_missing(
    ack, fake_slack_client, factory, slack_service, tmp_store
) -> None:
    """✅ CSV 가 미존재 (FileNotFoundError) → 헤더 + 새 행 작성."""
    # tmp_store 기본 fixture 가 헤더만 있는 빈 CSV 를 만들어둠. 미존재 케이스로 만들기 위해 삭제.
    csv_path = tmp_store / "writing_participation.csv"
    csv_path.unlink()

    user = factory.make_user(user_id="U_NEW", name="새유저")
    body = make_view_body(user_id="U_NEW", callback_id="writing_participation_view")

    await wp_events.submit_writing_participation_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        user=user,
        service=slack_service,
    )

    rows = _read_wp_csv(csv_path)
    assert len(rows) == 1
    assert rows[0]["user_id"] == "U_NEW"
    assert rows[0]["name"] == "새유저"
    assert rows[0]["is_writing_participation"] == "True"
    assert rows[0]["created_at"]  # 빈 문자열이 아님
    fake_slack_client.chat_postMessage.assert_awaited_once()
    kwargs = fake_slack_client.chat_postMessage.await_args.kwargs
    assert kwargs["channel"] == "U_NEW"
    assert "글쓰기 참여 신청을 완료" in kwargs["text"]


@pytest.mark.asyncio
async def test_submit_appends_new_row_when_user_not_in_existing_csv(
    ack, fake_slack_client, factory, slack_service, tmp_store, csv_writer_helper
) -> None:
    """✅ 다른 user_id 만 있는 CSV → 새 행 append."""
    csv_path = tmp_store / "writing_participation.csv"
    csv_writer_helper(
        csv_path,
        WP_HEADER,
        [
            {
                "user_id": "U_OLD",
                "name": "기존유저",
                "created_at": "2025-01-01 09:00:00",
                "is_writing_participation": "True",
            }
        ],
    )

    user = factory.make_user(user_id="U_NEW", name="새유저")
    body = make_view_body(user_id="U_NEW")

    await wp_events.submit_writing_participation_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        user=user,
        service=slack_service,
    )

    rows = _read_wp_csv(csv_path)
    assert len(rows) == 2
    user_ids = {r["user_id"] for r in rows}
    assert user_ids == {"U_OLD", "U_NEW"}
    new_row = next(r for r in rows if r["user_id"] == "U_NEW")
    assert new_row["name"] == "새유저"
    assert new_row["is_writing_participation"] == "True"


@pytest.mark.asyncio
async def test_submit_updates_existing_row_with_empty_created_at(
    ack, fake_slack_client, factory, slack_service, tmp_store, csv_writer_helper
) -> None:
    """✅ 기존 행 존재 (created_at 빈 문자열) → name 갱신 + created_at 채움 + 플래그 True."""
    csv_path = tmp_store / "writing_participation.csv"
    csv_writer_helper(
        csv_path,
        WP_HEADER,
        [
            {
                "user_id": "U_X",
                "name": "이전이름",
                "created_at": "",  # 비어있음 → 채워져야 함
                "is_writing_participation": "False",
            }
        ],
    )

    user = factory.make_user(user_id="U_X", name="새이름")
    body = make_view_body(user_id="U_X")

    await wp_events.submit_writing_participation_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        user=user,
        service=slack_service,
    )

    rows = _read_wp_csv(csv_path)
    assert len(rows) == 1
    assert rows[0]["user_id"] == "U_X"
    assert rows[0]["name"] == "새이름"  # 이름 최신화
    assert rows[0]["created_at"]  # 비어있지 않음
    assert rows[0]["is_writing_participation"] == "True"


@pytest.mark.asyncio
async def test_submit_keeps_existing_created_at_when_already_set(
    ack, fake_slack_client, factory, slack_service, tmp_store, csv_writer_helper
) -> None:
    """🌀 기존 created_at 이 있으면 그대로 유지 (덮어쓰지 않음)."""
    csv_path = tmp_store / "writing_participation.csv"
    csv_writer_helper(
        csv_path,
        WP_HEADER,
        [
            {
                "user_id": "U_X",
                "name": "기존",
                "created_at": "2024-12-01 09:00:00",
                "is_writing_participation": "False",
            }
        ],
    )

    user = factory.make_user(user_id="U_X", name="새이름")
    body = make_view_body(user_id="U_X")

    await wp_events.submit_writing_participation_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        user=user,
        service=slack_service,
    )

    rows = _read_wp_csv(csv_path)
    assert rows[0]["created_at"] == "2024-12-01 09:00:00"
    assert rows[0]["name"] == "새이름"
    assert rows[0]["is_writing_participation"] == "True"


@pytest.mark.asyncio
async def test_submit_fills_missing_columns(
    ack, fake_slack_client, factory, slack_service, tmp_store
) -> None:
    """🌀 컬럼이 누락된 CSV → 누락 컬럼 자동 채움 후 행 추가."""
    csv_path = tmp_store / "writing_participation.csv"
    # is_writing_participation 컬럼이 누락된 CSV
    df = pd.DataFrame([{"user_id": "U_OLD", "name": "기존", "created_at": "2025-01-01 09:00:00"}])
    df.to_csv(csv_path, index=False, quoting=csv.QUOTE_ALL)

    user = factory.make_user(user_id="U_NEW", name="새유저")
    body = make_view_body(user_id="U_NEW")

    await wp_events.submit_writing_participation_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        user=user,
        service=slack_service,
    )

    rows = _read_wp_csv(csv_path)
    assert len(rows) == 2
    # 모든 행이 컬럼 4개를 가져야 한다
    for row in rows:
        for col in WP_HEADER:
            assert col in row
    new_row = next(r for r in rows if r["user_id"] == "U_NEW")
    assert new_row["is_writing_participation"] == "True"


@pytest.mark.asyncio
async def test_submit_sends_dm_message(
    ack, fake_slack_client, factory, slack_service, tmp_store
) -> None:
    """✅ 신청 완료 후 DM 메시지 전송 (글쓰기 채널 안내)."""
    user = factory.make_user(user_id="U_X", name="유저")
    body = make_view_body(user_id="U_X")

    await wp_events.submit_writing_participation_view(
        ack=ack,
        body=body,
        client=fake_slack_client,
        user=user,
        service=slack_service,
    )

    fake_slack_client.chat_postMessage.assert_awaited_once()
    kwargs = fake_slack_client.chat_postMessage.await_args.kwargs
    assert kwargs["channel"] == "U_X"
    assert "글쓰기 참여 신청을 완료" in kwargs["text"]
