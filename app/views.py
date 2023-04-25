from app.client import SpreadSheetClient
from app.config import PASS_VIEW, SUBMIT_VIEW, SEARCH_VIEW, settings
from slack_bolt.async_app import AsyncApp
from app.db import create_log_file, fetch_db, upload_logs

from app.services import user_content_service
from app.utils import print_log


slack = AsyncApp(token=settings.BOT_TOKEN)


@slack.event("message")
async def handle_message_event(ack, body) -> None:
    await ack()


def _start_log(body: dict[str, str], type: str) -> str:
    return f"{body.get('user_id')}({body.get('channel_id')}) 님이 {type} 를 시작합니다."


@slack.command("/제출")
async def submit_command(ack, body, logger, say, client) -> None:
    print_log(_start_log(body, "submit"))
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
        print_log(message, str(e))
        return None


@slack.command("/패스")
async def pass_command(ack, body, logger, say, client) -> None:
    print_log(_start_log(body, "pass"))
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
        print_log(message, str(e))
        return None


@slack.command("/제출내역")
async def history_command(ack, body, logger, say, client) -> None:
    print_log(_start_log(body, "history"))
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
        fetch_db(sheet_client)
        upload_logs(sheet_client)
        create_log_file(sheet_client)
        await client.chat_postMessage(channel=body["user_id"], text="DB sync 완료")
    except ValueError as e:
        await client.chat_postMessage(channel=body["user_id"], text=str(e))


@slack.command("/검색")
async def search_command(ack, body, logger, say, client) -> None:
    print_log(_start_log(body, "serach"))
    await ack()
    await user_content_service.open_search_modal(body, client, PASS_VIEW)


@slack.view("submit_search")
async def handle_view_submission(ack, body, client, view, logger):
    # TODO: 로그 리팩터링하기
    user_body = {"user_id": body.get("user", {}).get("id")}
    print_log(_start_log(user_body, "submit_search"))
    await ack()

    users = user_content_service.fetch()

    name = _get_name(body)
    if name:
        results = [
            content for user in users if user.name == name for content in user.contents
        ]
    else:
        results = [content for user in users for content in user.contents]

    category = _get_category(body)
    if category != "전체":
        results = [content for content in results if content.category == category]

    # TODO: 검색 되돌리기 추가
    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "back_to_search_view",
            "title": {"type": "plain_text", "text": f"{len(results)}개의 글을 검색하였습니다 🔍"},
            "submit": {"type": "plain_text", "text": "다시 찾기"},
            "type": "modal",
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "plain_text", "text": "You updated the modal!"},
                },
                {
                    "type": "image",
                    "image_url": "https://media.giphy.com/media/SVZGEcYt7brkFUyU90/giphy.gif",
                    "alt_text": "Yay! The modal was updated",
                },
            ],
        },
    )


@slack.view("back_to_search_view")
async def search_command(ack, body, logger, say, client) -> None:
    # TODO: 로그 리팩터링하기
    user_body = {"user_id": body.get("user", {}).get("id")}
    print_log(_start_log(user_body, "back_to_search_view"))
    await ack()
    await user_content_service.open_search_modal(body, client, PASS_VIEW)


def _get_category(body):
    category = (
        body.get("view", {})
        .get("state", {})
        .get("values", {})
        .get("category_search", {})
        .get("chosen_category", {})
        .get("selected_option", {})
        .get("value", "전체")
    )

    return category


def _get_name(body):
    name = (
        body.get("view", {})
        .get("state", {})
        .get("values", {})
        .get("author_search", {})
        .get("author_name", {})
        .get("value", "")
    )

    return name
