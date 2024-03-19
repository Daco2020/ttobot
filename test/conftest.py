import pytest

from app.slack.repositories import SlackRepository
from app.slack.services import SlackReminderService


@pytest.fixture
def slack_repo() -> SlackRepository:
    return SlackRepository()


@pytest.fixture
def slack_remind_service(slack_repo: SlackRepository) -> SlackReminderService:
    return SlackReminderService(slack_repo)


class FakeAsyncWebClient:
    def __init__(self) -> None: ...

    async def chat_postMessage(self, **kwargs) -> None: ...
class FakeSlackApp:
    def __init__(self) -> None:
        self._async_client = FakeAsyncWebClient()

    @property
    def client(self) -> FakeAsyncWebClient:
        return self._async_client


@pytest.fixture
def slack_app() -> FakeSlackApp:
    return FakeSlackApp()
