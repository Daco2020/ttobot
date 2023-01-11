import os
import re


from dotenv import load_dotenv


from slack_bolt.async_app import AsyncApp

from app.services import slack_service
from etc.sheet import write_worksheet


load_dotenv()

slack = AsyncApp(
    token=os.environ.get("BOT_TOKEN"),
    # signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
)

SUBMIT_VIEW = "submit_view"
url_regex = r"((http|https):\/\/)?[a-zA-Z0-9.-]+(\.[a-zA-Z]{2,})"


@slack.command("/제출")
async def submit_command(ack, body, logger, say, client) -> None:
    await ack()
    await slack_service.submit_modal_open(body, client, SUBMIT_VIEW)


@slack.view(SUBMIT_VIEW)
async def submit_view(ack, body, client, view, logger, say) -> None:
    await ack()
    submission = slack_service.get_submission(body, view)

    try:
        await _validation_url(ack, submission.content_url)
    except ValueError:
        return

    write_worksheet(submission)
    await slack_service.send_chat_message(client, view, logger, submission)


async def _validation_url(ack, content_url) -> None:
    if not re.match(url_regex, content_url):
        errors = {}
        errors["content"] = "링크는 url 주소여야 합니다."
        await ack(response_action="errors", errors=errors)
        raise ValueError


@slack.command("/패스")
async def pass_command(ack, body, logger, say, client) -> None:
    await ack()
    await slack_service.pass_modal_open()
