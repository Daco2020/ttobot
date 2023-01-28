from app.config import PASS_VIEW, settings, SUBMIT_VIEW
from slack_bolt.async_app import AsyncApp

from app.services import submission_service, pass_service


slack = AsyncApp(token=settings.BOT_TOKEN)


@slack.event("message")
async def handle_message_event(ack, body) -> None:
    await ack()


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


@slack.command("/제출내역")
async def history_command(ack, body, logger, say, client) -> None:
    # TODO: 슬랙 개인 디엠으로 본인의 제출내역을 보여준다.
    await ack()
    msg = "열심히 작업중 🔨💦"
    await client.chat_postMessage(channel=body["user_id"], text=msg)


@slack.command("/고장신고")
async def report_command(ack, body, logger, say, client) -> None:
    # TODO: 고장신고
    await ack()
    msg = "열심히 작업중 🔨💦"  # 고장신고 접수가 완료되었습니다. 24시간내에 답변드리겠습니다.
    await client.chat_postMessage(channel=body["user_id"], text=msg)
