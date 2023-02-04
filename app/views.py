from app.config import PASS_VIEW, settings, SUBMIT_VIEW
from slack_bolt.async_app import AsyncApp

from app.services import user_content_service


slack = AsyncApp(token=settings.BOT_TOKEN)


@slack.event("message")
async def handle_message_event(ack, body) -> None:
    await ack()


@slack.command("/제출")
async def submit_command(ack, body, logger, say, client) -> None:
    await ack()
    await user_content_service.open_submit_modal(body, client, SUBMIT_VIEW)


@slack.view(SUBMIT_VIEW)
async def submit_view(ack, body, client, view, logger, say) -> None:
    await ack()
    try:
        user = await user_content_service.get_user(ack, body, view)
        content = await user_content_service.create_submit_content(
            ack, body, view, user
        )
    except ValueError:
        return None

    await user_content_service.send_chat_message(
        client, logger, content, user.channel_id
    )


@slack.command("/패스")
async def pass_command(ack, body, logger, say, client) -> None:
    await ack()
    await user_content_service.open_pass_modal(body, client, PASS_VIEW)


@slack.view(PASS_VIEW)
async def pass_view(ack, body, client, view, logger, say) -> None:
    await ack()
    try:
        user = await user_content_service.get_user(ack, body, view)
        content = await user_content_service.create_pass_content(ack, body, view, user)
    except ValueError:
        return None

    await user_content_service.send_chat_message(
        client, logger, content, user.channel_id
    )


@slack.command("/제출내역")
async def history_command(ack, body, logger, say, client) -> None:
    # TODO: 슬랙 개인 디엠으로 본인의 제출내역을 보여준다.
    await ack()
    message = "열심히 개발중 🔨💦"
    await client.chat_postMessage(channel=body["user_id"], text=message)
