from slack_sdk.web.async_client import AsyncWebClient
from app.slack.services import SlackService


async def example_command(
    ack, body, say, client: AsyncWebClient, user_id: str, service: SlackService
) -> None:
    """예시 명령어입니다."""
    await ack()
