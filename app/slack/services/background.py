from app.constants import remind_message
from app.logging import log_event
from app.models import User
from app.slack.repositories import SlackRepository


from slack_bolt.async_app import AsyncApp
from app.config import settings


import asyncio


class BackgroundService:
    def __init__(self, repo: SlackRepository) -> None:
        self._repo = repo

    async def send_reminder_message_to_user(self, slack_app: AsyncApp) -> None:
        """사용자에게 리마인드 메시지를 전송합니다."""
        users = self._repo.fetch_users()

        target_users: list[User] = []
        for user in users:
            if user.cohort != "10기":  # 10기 외의 사용자 제외
                continue
            if user.channel_name == "-":  # 채널 이름이 없는 경우 제외
                continue
            if user.is_submit:  # 이미 제출한 경우 제외
                continue

            target_users.append(user)

        for user in target_users:
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

        await slack_app.client.chat_postMessage(
            channel=settings.ADMIN_CHANNEL,
            text=f"총 {len(target_users)} 명에게 리마인드 메시지를 전송했습니다.",
        )
