from app.config import PASS_VIEW, settings, SUBMIT_VIEW
from slack_bolt.async_app import AsyncApp

from app.services import submission_service, pass_service


slack = AsyncApp(token=settings.BOT_TOKEN)


@slack.command("/제출")
async def submit_command(ack, body, logger, say, client) -> None:
    await ack()
    await submission_service.open_modal(body, client, SUBMIT_VIEW)


@slack.view(SUBMIT_VIEW)
async def submit_view(ack, body, client, view, logger, say) -> None:
    await ack()
    try:
        submission = await submission_service.get(ack, body, view)
    except ValueError:
        return None

    submission_service.submit(submission)
    await submission_service.send_chat_message(client, view, logger, submission)


@slack.command("/패스")
async def pass_command(ack, body, logger, say, client) -> None:
    await ack()
    await pass_service.open_modal(body, client, PASS_VIEW)


@slack.view(PASS_VIEW)
async def pass_view(ack, body, client, view, logger, say) -> None:
    await ack()
    try:
        pass_ = await pass_service.get(ack, body, view)
    except ValueError:
        return None

    pass_service.submit(pass_)
    await pass_service.send_chat_message(client, view, logger, pass_)
