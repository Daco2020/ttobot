import datetime
import os


from dotenv import load_dotenv

from slack_bolt.async_app import AsyncApp
from app.services import slack_service
from etc.sheet import write_worksheet


load_dotenv()

slack = AsyncApp(
    token=os.environ.get("BOT_TOKEN"),
    # signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
)


# @slack.event("app_mention")
# async def who_am_i(ack, event, client, message, say) -> None:
#     await ack()
#     await say("글을 제출하는 명령어는 `/제출` 에요\n글을 패스하는 명령어는 `/패스` 에요")


# @slack.event("message")
# async def handle_message_event(ack, body: dict[str, Any]) -> None:
#     await ack()

SUBMIT_VIEW = "submit_view"


@slack.command("/제출")
async def submit_command(ack, body, logger, say, client) -> None:
    await ack()
    await slack_service.submit_modal_open(body, client, SUBMIT_VIEW)


@slack.view(SUBMIT_VIEW)
async def submit_view(ack, body, client, view, logger, say) -> None:
    # TODO: 유효성 검사 함수 분리
    content_url = view["state"]["values"]["content"]["url_text_input-action"]["value"]
    category = view["state"]["values"]["category"]["static_select-action"][
        "selected_option"
    ]["value"]
    raw_tag = view["state"]["values"]["tag"]["dreamy_input"]["value"]
    description = view["state"]["values"]["description"]["plain_text_input-action"][
        "value"
    ]
    # TODO: URL 정규표현식 추가하기 / 길이는 5자 이상
    errors = {}
    if content_url is not None and len(content_url) <= 10:
        errors["content"] = "열 글자 이상의 url 주소여야 합니다."
    if len(errors) > 0:
        await ack(response_action="errors", errors=errors)
        return

    await ack()

    username = body["user"]["username"]
    dt = datetime.datetime.strftime(datetime.datetime.now(), "%Y-%m-%d %H:%M:%S")
    write_worksheet(username, content_url, dt, category, raw_tag)

    # TODO: 메세지 생성 함수 분리
    msg = ""
    user = body["user"]["id"]
    tag = ""
    if raw_tag:
        tag = " #".join(raw_tag.split(","))
    try:
        msg = f"<@{user}>님 제출 완료🎉\n\n💬 '{description}'\n\ncategory : {category}\ntag : #{tag}\nlink : {content_url}"
    except Exception as e:
        raise ValueError(str(e))

    # Message the user
    channal = view["private_metadata"]
    try:
        await client.chat_postMessage(channel=channal, text=msg)
    except Exception as e:
        logger.exception(f"Failed to post a message {e}")


@slack.command("/패스")
async def pass_command(ack, body, logger, say, client) -> None:
    await ack()
    await slack_service.pass_modal_open()
