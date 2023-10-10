from app.client import SpreadSheetClient
from app.config import settings
from app.services import user_content_service
from app.store import sync_store


async def handle_mention(body, say, client):
    """앱 멘션을 처리합니다."""
    user = body["event"]["user"]
    await say(f"{user} mentioned your app")


async def get_deposit(ack, body, say, client, user_id: str) -> None:
    """예치금을 조회합니다."""
    await ack()

    user = user_content_service.get_user_not_valid(body["user_id"])

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {"type": "plain_text", "text": f"{user.name}님의 예치금 현황"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"현재 남은 예치금은 {format(user.deposit, ',d')} 원 입니다.\n\n*<{settings.DEPOSIT_SHEETS_URL}|{'예치금 현황 자세히 확인하기'}>*",  # noqa E501
                    },
                },
            ],
        },
    )


async def history_command(ack, body, say, client, user_id: str) -> None:
    """제출 내역을 조회합니다."""
    await ack()
    submit_history = user_content_service.get_submit_history(body["user_id"])

    user = user_content_service.get_user_not_valid(body["user_id"])
    round, due_date = user.get_due_date()
    guide_message = f"\n*현재 회차는 {round}회차, 마감일은 {due_date} 이에요."

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {"type": "plain_text", "text": f"{user.name}님의 제출 내역"},
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": submit_history},
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


async def admin_command(ack, body, say, client, user_id: str) -> None:
    """관리자 메뉴를 조회합니다."""
    await ack()
    # TODO: 추후 관리자 메뉴 추가
    try:
        user_content_service.validate_admin_user(body["user_id"])
        await client.chat_postMessage(channel=body["user_id"], text="store sync 완료")
        sheet_client = SpreadSheetClient()
        sheet_client.push_backup()
        sync_store(sheet_client)
        sheet_client.upload_logs()
        sheet_client.create_log_file()
    except ValueError as e:
        await client.chat_postMessage(channel=body["user_id"], text=str(e))
