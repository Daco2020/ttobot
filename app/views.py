from app.client import SpreadSheetClient
from app.config import PASS_VIEW, settings, SUBMIT_VIEW
from slack_bolt.async_app import AsyncApp
from app.db import sync_db

from app.services import user_content_service
from app.utils import now_dt


slack = AsyncApp(token=settings.BOT_TOKEN)


@slack.event("message")
async def handle_message_event(ack, body) -> None:
    await ack()


def log_command(body: dict[str, str], type: str):
    user_id = body.get("user_id")
    channel_id = body.get("channel_id")
    print(f"type: {type}, user: {user_id}, channel: {channel_id}, time: {now_dt()}")


@slack.command("/제출")
async def submit_command(ack, body, logger, say, client) -> None:
    log_command(body, "submit")
    await ack()
    await user_content_service.open_submit_modal(body, client, SUBMIT_VIEW)


@slack.view(SUBMIT_VIEW)
async def submit_view(ack, body, client, view, logger, say) -> None:
    await ack()
    user_id = body["user"]["id"]
    channel_id = view["private_metadata"]

    try:
        user = user_content_service.get_user(user_id, channel_id)
        content = await user_content_service.create_submit_content(
            ack, body, view, user
        )
        await client.chat_postMessage(
            channel=channel_id, text=user_content_service.get_chat_message(content)
        )
    except Exception as e:
        message = f"{user.name}({user.channel_name}) 님의 제출이 실패하였습니다."
        print(message, now_dt(), str(e))
        return None


@slack.command("/패스")
async def pass_command(ack, body, logger, say, client) -> None:
    log_command(body, "pass")
    await ack()
    await user_content_service.open_pass_modal(body, client, PASS_VIEW)


@slack.view(PASS_VIEW)
async def pass_view(ack, body, client, view, logger, say) -> None:
    await ack()
    user_id = body["user"]["id"]
    channel_id = view["private_metadata"]

    try:
        user = user_content_service.get_user(user_id, channel_id)
        content = await user_content_service.create_pass_content(ack, body, view, user)
        await client.chat_postMessage(
            channel=channel_id, text=user_content_service.get_chat_message(content)
        )
    except Exception as e:
        message = f"{user.name}({user.channel_name}) 님의 패스가 실패하였습니다."
        print(message, now_dt(), str(e))
        return None


@slack.command("/제출내역")
async def history_command(ack, body, logger, say, client) -> None:
    await ack()
    submit_history = user_content_service.get_submit_history(body["user_id"])
    await client.chat_postMessage(channel=body["user_id"], text=submit_history)


@slack.command("/관리자")
async def admin_command(ack, body, logger, say, client) -> None:
    # TODO: 추후 관리자 메뉴 추가
    await ack()
    try:
        user_content_service.validate_admin_user(body["user_id"])
        sheet_client = SpreadSheetClient()
        sync_db(sheet_client)
        await client.chat_postMessage(channel=body["user_id"], text="DB sync 완료")
    except ValueError as e:
        await client.chat_postMessage(channel=body["user_id"], text=str(e))
