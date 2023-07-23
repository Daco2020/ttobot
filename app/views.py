import re
from typing import Any
from app import models
from app import config
from app.client import SpreadSheetClient
from app.config import ANIMAL_TYPE, PASS_VIEW, SUBMIT_VIEW, settings
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

        # TODO: 모코숲 로직 추후 제거
        animal = ANIMAL_TYPE[user.animal_type]

        text = user_content_service.get_chat_message(content, animal)
        await client.chat_postMessage(
            channel=channel_id,
            blocks=[
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "소개 보기"},
                            "action_id": "intro_modal",
                            "value": user.user_id,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "이전 작성글 보기"},
                            "action_id": "contents_modal",
                            "value": user.user_id,
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text,
                    },
                },
            ],
        )
    except Exception as e:
        message = f"{user.name}({user.channel_name}) 님의 제출이 실패하였습니다."
        print_log(message, str(e))
        return None


@slack.action("intro_modal")
async def open_intro_modal(ack, body, client, view, logger):
    await ack()

    user_body = {"user_id": body.get("user_id")}
    print_log(_start_log(user_body, "intro_modal"))

    user_id = body["actions"][0]["value"]
    user = user_content_service.get_user_not_valid(user_id)
    # TODO: 모코숲 로직 추후 제거
    animal = ANIMAL_TYPE[user.animal_type]

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {
                "type": "plain_text",
                # "text": f"{user.name}님의 소개",
                # TODO: 모코숲 로직 추후 제거
                "text": f"{animal['emoji']}{animal['name']} {user.name}님의 소개",
            },
            "close": {"type": "plain_text", "text": "닫기"},
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": user.intro.replace("\\n", "\n")},
                }
            ],
        },
    )


@slack.action("contents_modal")
async def contents_modal(ack, body, client, view, logger):
    await ack()

    user_body = {"user_id": body.get("user_id")}
    print_log(_start_log(user_body, "contents_modal"))

    user_id = body["actions"][0]["value"]
    user = user_content_service.get_user_not_valid(user_id)

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {"type": "plain_text", "text": f"{user.name}님의 작성글"},
            "close": {"type": "plain_text", "text": "닫기"},
            "blocks": _fetch_blocks(user.contents),
        },
    )


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

        # TODO: 모코숲 로직 추후 제거
        animal = ANIMAL_TYPE[user.animal_type]

        await client.chat_postMessage(
            channel=channel_id,
            text=user_content_service.get_chat_message(content, animal),
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


@slack.command("/예치금")
async def get_deposit(ack, body, logger, say, client) -> None:
    print_log(_start_log(body, "deposit"))
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
                        "text": f"현재 남은 예치금은 {format(user.deposit, ',d')} 원 입니다.\n\n*<{settings.DEPOSIT_SHEETS_URL}|{'예치금 현황 자세히 확인하기'}>*",
                    },
                },
            ],
        },
    )


@slack.command("/관리자")
async def admin_command(ack, body, logger, say, client) -> None:
    # TODO: 추후 관리자 메뉴 추가
    await ack()
    try:
        user_content_service.validate_admin_user(body["user_id"])
        sheet_client = SpreadSheetClient()
        sheet_client.push_backup()
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
async def submit_search(ack, body, client, view, logger):
    # TODO: 로그 리팩터링하기
    user_body = {"user_id": body.get("user", {}).get("id")}
    print_log(_start_log(user_body, "submit_search"))
    await ack()

    name = _get_name(body)
    category = _get_category(body)
    keyword = _get_keyword(body)

    contents = user_content_service.fetch_contents(keyword, name, category)

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "back_to_search_view",
            "title": {"type": "plain_text", "text": f"총 {len(contents)} 개의 글이 있습니다. 🔍"},
            "submit": {"type": "plain_text", "text": "다시 찾기"},
            "blocks": _fetch_blocks(contents),
        },
    )


def _fetch_blocks(contents: list[models.Content]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    blocks.append(
        {
            "type": "section",
            "text": {"type": "plain_text", "text": "결과는 최대 20개까지만 표시합니다."},
        },
    )
    for content in contents:
        if content.content_url:
            blocks.append({"type": "divider"})
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*<{content.content_url}|{re.sub('<|>', '', content.title)}>*",
                    },
                    "accessory": {
                        "type": "overflow",
                        "action_id": "overflow-action",
                        "options": [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "👍🏼 추천(추후 도입 예정)",
                                    "emoji": True,
                                },
                                "value": "like",
                            },
                        ],
                    },
                }
            )
            tags = f"> 태그: {' '.join(content.tags.split('#'))}" if content.tags else " "
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"> 카테고리: {content.category}"},
                        {"type": "mrkdwn", "text": tags},
                    ],
                }
            )
        if len(blocks) > 60:
            return blocks
    return blocks


@slack.view("back_to_search_view")
async def back_to_search_view(ack, body, logger, say, client) -> None:
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


def _get_keyword(body):
    name = (
        body.get("view", {})
        .get("state", {})
        .get("values", {})
        .get("keyword_search", {})
        .get("keyword", {})
        .get("value", "")
    )
    return name


# TODO: 모코숲 로직 추후 제거
@slack.command("/모코숲")
async def guide_command(ack, body, logger, say, client) -> None:
    print_log(_start_log(body, "guide"))
    await ack()
    # await user_content_service.open_submit_modal(body, client, SUBMIT_VIEW)

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {
                "type": "plain_text",
                "text": f"모여봐요 코드의 숲",
            },
            "close": {"type": "plain_text", "text": "닫기"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "글쓰기를 좋아하는 동물들이 코드의 숲에 모였다?\n우리가 함께 만들어 갈 여름 이야기, 모여봐요 코드의 숲! 🍃\n\n\n*설명*\n- 기존 2주 1글쓰기 규칙을 유지해요.\n- ‘모코숲’ 채널에 함께 모여 활동해요.\n- ‘모코숲’ 채널에 들어오면 자신이 어떤 동물인지 알 수 있어요.\n- 글만 올리면 심심하죠? 수다와 각종 모임 제안도 가능(권장)해요!\n\n\n*일정*\n- 7월 23일 일요일 ‘모코숲’이 열려요!\n- 7월 23일부터 9월 24일까지 두 달간 진행합니다.\n- 첫 번째 글 마감은 7월 30일 이에요! (이후 2주 간격 제출)\n\n\n*동물 소개*\n- 🐈 '고양이'는 여유롭고 독립된 일상을 즐겨요.\n- 🦦 '해달'은 기술과 도구에 관심이 많고 문제해결을 좋아해요.\n- 🦫 '비버'는 명확한 목표와 함께 협업을 즐겨요.\n- 🐘 '코끼리'는 커리어에 관심이 많고 자부심이 넘쳐요.\n- 🐕 '강아지'는 조직문화에 관심이 많고 팀워크를 중요하게 여겨요.\n- 🐢 '거북이'는 늦게 시작했지만 끝까지 포기하지 않아요.",
                    },
                }
            ],
        },
    )


# TODO: 모코숲 로직 추후 제거
@slack.event("member_joined_channel")
async def send_welcome_message(event, say):
    if event["channel"] == "C05K0RNQZA4":
        try:
            user_id = event["user"]
            user = user_content_service.get_user_not_valid(user_id)
            animal = ANIMAL_TYPE[user.animal_type]

            message = (
                f"\n>>>{animal['emoji']}{animal['name']} <@{user_id}>님이 🌳모코숲🌳에 입장했습니다👏🏼"
            )
            await say(
                channel=event["channel"],
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": message,
                        },
                        "accessory": {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "소개 보기"},
                            "action_id": "intro_modal",
                            "value": user.user_id,
                        },
                    },
                ],
            )
        except Exception as e:
            print_log(e)
            pass
