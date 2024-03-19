import pytest

from app.slack.repositories import SlackRepository
from app.slack.services import SlackRemindService


@pytest.fixture
def slack_repo() -> SlackRepository:
    return SlackRepository()


@pytest.fixture
def slack_remind_service(slack_repo: SlackRepository) -> SlackRemindService:
    return SlackRemindService(slack_repo)
