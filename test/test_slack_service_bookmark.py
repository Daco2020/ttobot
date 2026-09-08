"""SlackService.update_bookmark 가 repo 에 user_id 를 넘기는지 (호출자 연결, worklog 021)."""

from __future__ import annotations

from unittest.mock import MagicMock

from app import models
from app.slack.services.base import SlackService


def test_service_passes_user_id_to_repo() -> None:
    """결합: 서비스 → 저장소 호출에 user_id 가 포함된다."""
    repo = MagicMock()
    repo.get_bookmark.return_value = None
    service = SlackService(repo=repo, user=MagicMock())

    service.update_bookmark("U1", "ts1", new_status=models.BookmarkStatusEnum.DELETED)

    repo.update_bookmark.assert_called_once_with(
        "U1", "ts1", "", models.BookmarkStatusEnum.DELETED
    )
