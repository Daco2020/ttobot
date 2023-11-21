from app.client import SpreadSheetClient
from app.config import settings
from app.slack.services import SlackService
from app.store import Store


# async def handle_mention(body, say, client) -> None:
#     """앱 멘션을 처리합니다."""
#     # TODO: 추후 멘션에 대한 처리 추가
#     user = body["event"]["user"]
#     await say(f"{user} mentioned your app")


async def get_deposit(
    ack, body, say, client, user_id: str, service: SlackService
) -> None:
    """예치금을 조회합니다."""
    await ack()

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {"type": "plain_text", "text": f"{service.user.name}님의 예치금 현황"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"현재 남은 예치금은 {format(service.user.deposit, ',d')} 원 입니다.\n\n*<{settings.DEPOSIT_SHEETS_URL}|{'예치금 현황 자세히 확인하기'}>*",  # noqa E501
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
            "title": {"type": "plain_text", "text": f"{service.user.name}님의 제출 내역"},
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
    try:
        if user_id not in settings.ADMIN_IDS:
            raise PermissionError("관리자 계정이 아닙니다.")
        await client.chat_postMessage(channel=body["user_id"], text="store sync 완료")
        sheet_client = SpreadSheetClient()
        store = Store(client=sheet_client)
        store.upload("logs")
        store.backup("contents")
        store.initialize_logs()
        store.pull()
    except ValueError as e:
        await client.chat_postMessage(channel=body["user_id"], text=str(e))
