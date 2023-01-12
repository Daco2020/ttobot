import os
import re


from dotenv import load_dotenv


from slack_bolt.async_app import AsyncApp

from app.services import submission_service, pass_service
from etc.sheet import write_worksheet


load_dotenv()

slack = AsyncApp(token=os.environ.get("BOT_TOKEN"))

SUBMIT_VIEW = "submit_view"
url_regex = r"((http|https):\/\/)?[a-zA-Z0-9.-]+(\.[a-zA-Z]{2,})"


@slack.command("/제출")
async def submit_command(ack, body, logger, say, client) -> None:
    await ack()
    await submission_service.open_modal(body, client, SUBMIT_VIEW)


@slack.view(SUBMIT_VIEW)
async def submit_view(ack, body, client, view, logger, say) -> None:
    await ack()
    submission = submission_service.get_submission(body, view)

    if not await _is_error_in_url(ack, submission.content_url):
        return None

    write_worksheet(submission)
    await submission_service.send_chat_message(client, view, logger, submission)


async def _is_error_in_url(ack, content_url) -> bool:
    if re.match(url_regex, content_url):
        return True
    else:
        errors = {}
        errors["content"] = "링크는 url 주소여야 합니다."
        await ack(response_action="errors", errors=errors)
        return False


@slack.command("/패스")
async def pass_command(ack, body, logger, say, client) -> None:
    await ack()
    await pass_service.open_modal()
