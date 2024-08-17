from app.client import SpreadSheetClient
from app.config import settings
from app.constants import HELP_TEXT
from app.slack.services import SlackService
from app.store import Store


async def handle_app_mention(ack, body, say, client) -> None:
    """앱 멘션 호출 시 도움말 메시지를 전송합니다."""
    await ack()


async def get_deposit(
    ack, body, say, client, user_id: str, service: SlackService
) -> None:
    """예치금을 조회합니다."""
    await ack()

    if not service.user.deposit:
        text = "현재 예치금 확인 중이에요."
    else:
        deposit_link = (
            f"\n\n*<{settings.DEPOSIT_SHEETS_URL}|{'예치금 현황 자세히 확인하기'}>*"
            if settings.DEPOSIT_SHEETS_URL
            else ""
        )
        text = (
            f"현재 남은 예치금은 {format(int(service.user.deposit), ',d')} 원 이에요."
            + deposit_link
        )

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {
                "type": "plain_text",
                "text": f"{service.user.name}님의 예치금 현황",
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text,
                    },
                },
            ],
        },
    )


async def history_command(
    ack, body, say, client, user_id: str, service: SlackService
) -> None:
    """제출 내역을 조회합니다."""
    await ack()

    round, due_date = service.user.get_due_date()
    guide_message = f"\n*현재 회차는 {round}회차, 마감일은 {due_date} 이에요."

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {
                "type": "plain_text",
                "text": f"{service.user.name}님의 제출 내역",
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": service.get_submit_history()},
                },
                {
                    "type": "divider",
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": guide_message},
                },
            ],
        },
    )


async def admin_command(
    ack, body, say, client, user_id: str, service: SlackService
) -> None:
    """관리자 메뉴를 조회합니다."""
    await ack()
    # TODO: 추후 관리자 메뉴 추가

    if user_id not in settings.ADMIN_IDS:
        raise PermissionError("`/관리자` 명령어는 관리자만 호출할 수 있어요. 🤭")
    try:
        await client.chat_postMessage(
            channel=settings.ADMIN_CHANNEL, text="store pull 시작"
        )
        sheet_client = SpreadSheetClient()
        store = Store(client=sheet_client)
        store.bulk_upload("logs")
        store.backup("contents")
        store.initialize_logs()
        store.pull()
        await client.chat_postMessage(
            channel=settings.ADMIN_CHANNEL, text="store pull 완료"
        )
    except Exception as e:
        await client.chat_postMessage(channel=settings.ADMIN_CHANNEL, text=str(e))


async def help_command(
    ack, body, say, client, user_id: str, channel_id: str, service: SlackService
) -> None:
    """도움말을 조회합니다."""
    await ack()

    # 또봇이 추가된 채널만 전송할 수 있기 때문에 개인 디엠으로 보내도록 통일.
    await client.chat_postEphemeral(
        channel=user_id,
        user=user_id,
        text=HELP_TEXT,
    )
