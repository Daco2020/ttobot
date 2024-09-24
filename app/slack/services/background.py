from app.constants import remind_message
from app.logging import log_event
from app.slack.repositories import SlackRepository


from slack_bolt.async_app import AsyncApp


import asyncio


class BackgroundService:
    def __init__(self, repo: SlackRepository) -> None:
        self._repo = repo

    async def send_reminder_message_to_user(self, slack_app: AsyncApp) -> None:
        """사용자에게 리마인드 메시지를 전송합니다."""
        users = self._repo.fetch_users()
        for user in users:
            if user.is_submit:
                continue
            if user.cohort == "8기":
                continue
            if user.cohort == "9기":
                continue
            if user.channel_name == "슬랙봇":
                continue

            log_event(
                actor="slack_reminder_service",
                event="send_reminder_message_to_user",
                type="reminder",
                description=f"{user.name} 님에게 리마인드 메시지를 전송합니다.",
            )

            await slack_app.client.chat_postMessage(
                channel=user.user_id,
                text=remind_message.format(user_name=user.name),
            )

            # 슬랙은 메시지 전송을 초당 1개를 권장하기 때문에 1초 대기합니다.
            # 참고문서: https://api.slack.com/methods/chat.postMessage#rate_limiting
            await asyncio.sleep(1)
