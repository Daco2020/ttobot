import ast
import asyncio
import re
from typing import Any
import requests
import orjson

from app.slack.components import static_select
from app.constants import CONTENTS_PER_PAGE, ContentCategoryEnum
from app.slack.exception import BotException, ClientException
from slack_sdk.web.async_client import AsyncWebClient

from app import models
from app.slack.services import SlackService


async def submit_command(
    ack,
    body,
    say,
    client,
    user_id: str,
    service: SlackService,
) -> None:
    """글 제출 시작"""
    await ack()

    # await service.open_submit_modal(
    #     body=body,
    #     client=client,
    #     view_name="submit_view",
    # )

    # TODO: 방학용 제출 모달
    service._check_channel(body["channel_id"])
    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "private_metadata": body["channel_id"],
            "callback_id": "submit_view",
            "title": {"type": "plain_text", "text": "또봇"},
            "submit": {"type": "plain_text", "text": "제출"},
            "blocks": [
                {
                    "type": "section",
                    "block_id": "required_section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "글또 방학기간에도 글을 제출할 수 있어요.😊",
                    },
                },
                {
                    "type": "input",
                    "block_id": "content_url",
                    "element": {
                        "type": "url_text_input",
                        "action_id": "url_text_input-action",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "노션은 하단의 '글 제목'을 필수로 입력해주세요.",
                            "emoji": True,
                        },
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "글 링크",
                        "emoji": True,
                    },
                },
                {
                    "type": "input",
                    "block_id": "category",
                    "label": {
                        "type": "plain_text",
                        "text": "카테고리",
                        "emoji": True,
                    },
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "글의 카테고리를 선택해주세요.",
                            "emoji": True,
                        },
                        "options": static_select.options(
                            [category.value for category in ContentCategoryEnum]
                        ),
                        "action_id": "static_select-category",
                    },
                },
                {"type": "divider"},
                {
                    "type": "input",
                    "block_id": "tag",
                    "label": {
                        "type": "plain_text",
                        "text": "태그",
                    },
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "dreamy_input",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "태그1,태그2,태그3, ... ",
                        },
                        "multiline": False,
                    },
                },
                {
                    "type": "input",
                    "block_id": "description",
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "plain_text_input-action",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "하고 싶은 말이 있다면 남겨주세요.",
                        },
                        "multiline": True,
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "하고 싶은 말",
                        "emoji": True,
                    },
                },
                {
                    "type": "input",
                    "block_id": "manual_title_input",
                    "label": {
                        "type": "plain_text",
                        "text": "글 제목(직접 입력)",
                    },
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "title_input",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "'글 제목'을 직접 입력합니다.",
                        },
                        "multiline": False,
                    },
                },
            ],
        },
    )


async def submit_view(
    ack,
    body,
    client: AsyncWebClient,
    view,
    say,
    user_id: str,
    service: SlackService,
) -> None:
    """글 제출 완료"""
    # 슬랙 앱이 구 버전일 경우 일부 block 이 사라져 키에러가 발생할 수 있음
    content_url = view["state"]["values"]["content_url"]["url_text_input-action"][
        "value"
    ]
    channel_id = view["private_metadata"]
    username = body["user"]["username"]

    try:
        service.validate_url(view, content_url)
        title = await service.get_title(view, content_url)
    except (ValueError, ClientException) as e:
        # 참고: ack 로 에러를 반환할 경우, 그전에 ack() 를 호출하지 않아야 한다.
        await ack(response_action="errors", errors={"content_url": str(e)})
        raise e

    await ack()

    try:
        content = await service.create_submit_content(
            title, content_url, username, view
        )
        # 해당 text 는 슬랙 활동 탭에서 표시되는 메시지이며, 누가 어떤 링크를 제출했는지 확인합니다.
        text = f"*<@{content.user_id}>님 제출 완료.* 링크 : *<{content.content_url}|{re.sub('<|>', '', title if content.title != 'title unknown.' else content.content_url)}>*"
        message = await client.chat_postMessage(
            channel=channel_id,
            text=text,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": service.get_chat_message(content),
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "자기소개 보기"},
                            "action_id": "intro_modal",
                            "value": service.user.user_id,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "이전 작성글 보기"},
                            "action_id": "contents_modal",
                            "value": service.user.user_id,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "북마크 추가📌"},
                            "action_id": "bookmark_modal",
                            "value": content.content_id,
                        },
                    ],
                },
            ],
        )
        content.ts = message.get("ts", "")
        await service.update_user_content(content)

        # TODO: 방학기간에 담소에도 글을 보낼지에 대한 메시지 전송 로직
        # 2초 대기하는 이유는 메시지 보다 더 먼저 전송 될 수 있기 때문임
        await asyncio.sleep(2)
        await client.chat_postEphemeral(
            user=user_id,
            channel=channel_id,
            text="여러분의 소중한 글을 더 많은 분들에게 보여드리고 싶어요. 자유로운 담소에도 전송하시겠어요?",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "🤗여러분의 소중한 글을 더 많은 분들에게 보여드리고 싶어요. \n자유로운 담소 채널에도 전송하시겠어요?",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "전송하기",
                            },
                            "action_id": "forward_message",
                            "value": content.ts,
                            "style": "primary",
                        }
                    ],
                },
            ],
        )

    except Exception as e:
        message = f"{service.user.name}({service.user.channel_name}) 님의 제출이 실패했어요. {str(e)}"  # type: ignore
        raise BotException(message)  # type: ignore


async def forward_message(
    ack,
    body,
    client: AsyncWebClient,
    view,
    user_id: str,
    service: SlackService,
) -> None:
    # TODO: 방학기간에 담소에도 글을 보낼지에 대한 메시지 전송 로직
    await ack()

    content_ts = body["actions"][0]["value"]
    source_channel = body["channel"]["id"]
    # target_channel = "C05J4FGB154"  # 자유로운 담소 채널 ID 테스트용
    target_channel = "C0672HTT36C"  # 자유로운 담소 채널 ID 운영용

    permalink_response = await client.chat_getPermalink(
        channel=source_channel, message_ts=content_ts
    )
    permalink = permalink_response["permalink"]
    content = service.get_content_by_ts(content_ts)

    # 담소 채널에 보내는 메시지
    text = f"<@{content.user_id}>님이 글을 공유했어요! \n👉 *<{permalink}|{content.title}>*"
    await client.chat_postMessage(channel=target_channel, text=text)

    # 나에게만 표시 메시지 수정하는 요청(slack bolt 에서는 지원하지 않음)
    requests.post(
        body["response_url"],
        json={
            "response_type": "ephemeral",
            "text": f"<#{target_channel}> 에 전송되었어요. 📨",
            "replace_original": True,
            # "delete_original": True, # 삭제도 가능
        },
    )


async def open_intro_modal(
    ack,
    body,
    client,
    view,
    user_id: str,
    service: SlackService,
) -> None:
    """다른 유저의 자기소개 확인"""
    await ack()

    other_user_id = body["actions"][0]["value"]
    other_user = service.get_other_user(other_user_id)

    if user_id == other_user_id:
        edit_intro_button = {
            "submit": {"type": "plain_text", "text": "자기소개 수정"},
            "callback_id": "edit_intro_view",
        }
    else:
        edit_intro_button = {}

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {
                "type": "plain_text",
                "text": f"{other_user.name}님의 소개",
            },
            **edit_intro_button,
            "close": {"type": "plain_text", "text": "닫기"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": other_user.intro.replace("\\n", "\n")
                        or "자기소개가 비어있어요. 😢",
                    },
                },
            ],
        },
    )


async def edit_intro_view(
    ack,
    body,
    client,
    view,
    say,
    user_id: str,
    service: SlackService,
) -> None:
    """자기소개 수정 시작"""
    await ack(
        {
            "response_action": "update",
            "view": {
                "type": "modal",
                "callback_id": "submit_intro_view",
                "title": {"type": "plain_text", "text": "자기소개 수정"},
                "submit": {"type": "plain_text", "text": "자기소개 제출"},
                "close": {"type": "plain_text", "text": "닫기"},
                "blocks": [
                    {
                        "type": "section",
                        "block_id": "required_section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "자신만의 개성있는 소개문구를 남겨주세요. 😉",
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "description",
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "edit_intro",
                            "multiline": True,
                            "max_length": 2000,
                            "placeholder": {
                                "type": "plain_text",
                                "text": f"{service.user.intro[:100]} ... ",
                            },
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "자기소개 내용",
                            "emoji": True,
                        },
                    },
                ],
            },
        }
    )


async def submit_intro_view(
    ack, body, client, view, say, user_id: str, service: SlackService
) -> None:
    """자기소개 수정 완료"""
    new_intro = view["state"]["values"]["description"]["edit_intro"]["value"] or ""
    service.update_user(user_id, new_intro=new_intro)
    await ack(
        {
            "response_action": "update",
            "view": {
                "type": "modal",
                "callback_id": "submit_intro_view",
                "title": {"type": "plain_text", "text": "자기소개 수정 완료"},
                "close": {"type": "plain_text", "text": "닫기"},
                "blocks": [
                    {
                        "type": "image",
                        "image_url": "https://media1.giphy.com/media/g9582DNuQppxC/giphy.gif",  # noqa E501
                        "alt_text": "success",
                    },
                    {
                        "type": "rich_text",
                        "elements": [
                            {
                                "type": "rich_text_section",
                                "elements": [
                                    {
                                        "type": "text",
                                        "text": "자기소개 수정이 완료되었습니다. 👏🏼👏🏼👏🏼\n다시 [자기소개 보기] 버튼을 통해 확인해보세요!",  # noqa E501
                                    }
                                ],
                            }
                        ],
                    },
                ],
            },
        }
    )


async def contents_modal(
    ack,
    body,
    client,
    view,
    user_id: str,
    service: SlackService,
) -> None:
    """다른 유저의 제출한 글 목록 확인"""
    await ack()

    other_user_id = body["actions"][0]["value"]
    other_user = service.get_other_user(other_user_id)

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {"type": "plain_text", "text": f"{other_user.name}님의 작성글"},
            "close": {"type": "plain_text", "text": "닫기"},
            "blocks": _fetch_blocks(other_user.contents),
        },
    )


async def bookmark_modal(
    ack,
    body,
    client,
    view,
    user_id: str,
    service: SlackService,
) -> None:
    # TODO: 글 검색에서 넘어온 경우 북마크 저장 후 검색 모달로 돌아가야 함
    """북마크 저장 시작"""
    await ack()

    actions = body["actions"][0]
    is_overflow = actions["type"] == "overflow"  # TODO: 분리필요
    if is_overflow:
        content_id = actions["selected_option"]["value"]
    else:
        content_id = actions["value"]

    bookmark = service.get_bookmark(user_id, content_id)
    view = get_bookmark_view(content_id, bookmark)
    if is_overflow:
        await client.views_update(view_id=body["view"]["id"], view=view)
    else:
        await client.views_open(trigger_id=body["trigger_id"], view=view)


def get_bookmark_view(
    content_id: str, bookmark: models.Bookmark | None
) -> dict[str, Any]:
    if bookmark is not None:
        # 이미 북마크가 되어 있다면 이를 사용자에게 알린다.
        view = {
            "type": "modal",
            "title": {"type": "plain_text", "text": "북마크"},
            "close": {"type": "plain_text", "text": "닫기"},
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "\n이미 북마크한 글이에요. 😉"},
                }
            ],
        }

    else:
        view = {
            "type": "modal",
            "private_metadata": content_id,
            "callback_id": "bookmark_view",
            "title": {"type": "plain_text", "text": "북마크"},
            "submit": {"type": "plain_text", "text": "북마크 추가"},
            "blocks": [
                {
                    "type": "section",
                    "block_id": "required_section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "\n북마크한 글은 `/북마크` 명령어로 확인할 수 있어요.",
                    },
                },
                {
                    "type": "input",
                    "block_id": "bookmark_note",
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "plain_text_input-action",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "북마크에 대한 메모를 남겨주세요.",
                        },
                        "multiline": True,
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "메모",
                        "emoji": True,
                    },
                },
            ],
        }

    return view


async def bookmark_view(
    ack,
    body,
    client,
    view,
    say,
    user_id: str,
    service: SlackService,
) -> None:
    """북마크 저장 완료"""
    await ack()

    content_id = view["private_metadata"]
    value = view["state"]["values"]["bookmark_note"]["plain_text_input-action"]["value"]
    note = value if value else ""  # 유저가 입력하지 않으면 None 으로 전달 된다.
    service.create_bookmark(user_id, content_id, note)

    await ack(
        {
            "response_action": "update",
            "view": {
                "type": "modal",
                "title": {"type": "plain_text", "text": "북마크"},
                "close": {"type": "plain_text", "text": "닫기"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "\n북마크를 추가했어요. 😉"},
                    }
                ],
            },
        }
    )


async def pass_command(
    ack,
    body,
    say,
    client,
    user_id: str,
    service: SlackService,
) -> None:
    """글 패스 시작"""
    await ack()

    await service.open_pass_modal(
        body=body,
        client=client,
        view_name="pass_view",
    )


async def pass_view(
    ack,
    body,
    client,
    view,
    say,
    user_id: str,
    service: SlackService,
) -> None:
    """글 패스 완료"""
    await ack()

    channel_id = view["private_metadata"]

    try:
        content = await service.create_pass_content(ack, body, view)
        message = await client.chat_postMessage(
            channel=channel_id,
            text=service.get_chat_message(content),
        )
        content.ts = message.get("ts", "")
        await service.update_user_content(content)
    except Exception as e:
        message = f"{service.user.name}({service.user.channel_name}) 님의 패스가 실패했어요. {str(e)}"
        raise BotException(message)


async def search_command(
    ack,
    body,
    say,
    client,
    user_id: str,
    service: SlackService,
) -> None:
    """글 검색 시작"""
    await ack()

    await service.open_search_modal(body, client)


async def submit_search(
    ack,
    body,
    client,
    view,
    user_id: str,
    service: SlackService,
) -> None:
    """글 검색 완료"""
    name = _get_name(body)
    category = _get_category(body)
    keyword = _get_keyword(body)

    contents = service.fetch_contents(keyword, name, category)

    await ack(
        {
            "response_action": "update",
            "view": {
                "type": "modal",
                "callback_id": "back_to_search_view",
                "title": {
                    "type": "plain_text",
                    "text": f"총 {len(contents)} 개의 글이 있어요. 🔍",
                },
                "submit": {"type": "plain_text", "text": "다시 검색"},
                "blocks": _fetch_blocks(contents),
            },
        }
    )


async def web_search(
    ack,
    body,
    client,
    view,
    user_id: str,
    service: SlackService,
) -> None:
    """웹 검색 시작"""
    await ack()


def _fetch_blocks(contents: list[models.Content]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": "결과는 최대 20개까지만 표시해요.",
            },  # TODO: 프론트 링크 붙이기
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
                        "text": f"*<{content.content_url}|{re.sub('<|>', '', content.title)}>*",  # noqa E501
                    },
                    "accessory": {
                        "type": "overflow",
                        "action_id": "bookmark_modal",
                        "options": [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "북마크 추가📌",
                                    "emoji": True,
                                },
                                "value": content.content_id,
                            },
                        ],
                    },
                }
            )
            tags = f"> 태그: {content.tags}" if content.tags else " "
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


async def back_to_search_view(
    ack,
    body,
    say,
    client,
    user_id: str,
    service: SlackService,
) -> None:
    """글 검색 다시 시작"""
    view = {
        "type": "modal",
        "callback_id": "submit_search",
        "title": {"type": "plain_text", "text": "글 검색 🔍"},
        "submit": {"type": "plain_text", "text": "검색"},
        "blocks": [
            {
                "type": "section",
                "block_id": "description_section",
                "text": {
                    "type": "mrkdwn",
                    "text": "원하는 조건의 글을 검색할 수 있어요.",
                },
            },
            {
                "type": "input",
                "block_id": "keyword_search",
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "keyword",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "키워드를 입력해주세요.",
                    },
                    "multiline": False,
                },
                "label": {
                    "type": "plain_text",
                    "text": "키워드",
                    "emoji": True,
                },
            },
            {
                "type": "input",
                "block_id": "author_search",
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "author_name",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "이름을 입력해주세요.",
                    },
                    "multiline": False,
                },
                "label": {
                    "type": "plain_text",
                    "text": "글 작성자",
                    "emoji": False,
                },
            },
            {
                "type": "input",
                "block_id": "category_search",
                "label": {"type": "plain_text", "text": "카테고리", "emoji": True},
                "element": {
                    "type": "static_select",
                    "action_id": "chosen_category",
                    "placeholder": {"type": "plain_text", "text": "카테고리 선택"},
                    "initial_option": {
                        "text": {"type": "plain_text", "text": "전체"},
                        "value": "전체",
                    },
                    "options": static_select.options(
                        [category.value for category in ContentCategoryEnum] + ["전체"]
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "웹으로 검색하시려면 [웹 검색] 버튼을 눌러주세요.",
                },
                "accessory": {
                    "type": "button",
                    "action_id": "web_search",
                    "text": {
                        "type": "plain_text",
                        "text": "웹 검색",
                    },
                    "url": "https://vvd.bz/d2HG",
                    "style": "primary",
                },
            },
        ],
    }

    await ack({"response_action": "update", "view": view})


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


def _get_name(body) -> str:
    name = (
        body.get("view", {})
        .get("state", {})
        .get("values", {})
        .get("author_search", {})
        .get("author_name", {})
        .get("value", "")
    )
    return name


def _get_keyword(body) -> str:
    keyword = (
        body.get("view", {})
        .get("state", {})
        .get("values", {})
        .get("keyword_search", {})
        .get("keyword", {})
        .get("value", "")
    ) or ""
    return keyword


async def bookmark_command(
    ack,
    body,
    say,
    client,
    user_id: str,
    service: SlackService,
) -> None:
    """북마크 조회"""
    await ack()

    bookmarks = service.fetch_bookmarks(user_id)
    content_ids = [bookmark.content_id for bookmark in bookmarks]
    contents = service.fetch_contents_by_ids(content_ids)
    content_matrix = _get_content_metrix(contents)

    view: dict[str, Any] = {
        "type": "modal",
        "title": {
            "type": "plain_text",
            "text": f"총 {len(contents)} 개의 북마크가 있어요.",
        },
        "blocks": _fetch_bookmark_blocks(content_matrix, bookmarks),
        "callback_id": "handle_bookmark_page_view",
    }

    private_metadata = dict()
    private_metadata = orjson.dumps({"page": 1}).decode("utf-8")

    if len(content_matrix) > 1:
        actions = {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "다음 페이지"},
                    "style": "primary",
                    "action_id": "next_bookmark_page_action",
                }
            ],
        }
        view["blocks"].append(actions)
    view["private_metadata"] = private_metadata
    await client.views_open(
        trigger_id=body["trigger_id"],
        view=view,
    )


async def handle_bookmark_page(
    ack,
    body,
    say,
    client: AsyncWebClient,
    user_id: str,
    service: SlackService,
) -> None:
    """북마크 페이지 이동"""
    await ack()

    bookmarks = service.fetch_bookmarks(user_id)
    content_ids = [bookmark.content_id for bookmark in bookmarks]
    contents = service.fetch_contents_by_ids(content_ids)
    content_matrix = _get_content_metrix(contents)
    action_id = body["actions"][0]["action_id"] if body.get("actions") else None
    private_metadata = body.get("view", {}).get("private_metadata", {})
    page = orjson.loads(private_metadata).get("page", 1) if private_metadata else 1

    if action_id == "next_bookmark_page_action":
        page += 1
    elif action_id == "prev_bookmark_page_action":
        page -= 1

    view: dict[str, Any] = {
        "type": "modal",
        "title": {
            "type": "plain_text",
            "text": f"총 {len(contents)} 개의 북마크가 있어요.",
        },
        "blocks": _fetch_bookmark_blocks(content_matrix, bookmarks, page=page),
        "callback_id": "handle_bookmark_page_view",
        "private_metadata": orjson.dumps({"page": page}).decode("utf-8"),
    }

    button_elements = []
    if page != 1:
        button_elements.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "이전 페이지"},
                "style": "primary",
                "action_id": "prev_bookmark_page_action",
            }
        )
    if len(content_matrix) > page:
        button_elements.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "다음 페이지"},
                "style": "primary",
                "action_id": "next_bookmark_page_action",
            }
        )

    if button_elements:
        button_actions = {"type": "actions", "elements": button_elements}
        view["blocks"].append(button_actions)
    if body["type"] == "block_actions":
        await client.views_update(
            view_id=body["view"]["id"],
            view=view,
        )
    else:
        await client.views_open(
            trigger_id=body["trigger_id"],
            view=view,
        )


def _fetch_bookmark_blocks(
    content_matrix: dict[int, list[models.Content]],
    bookmarks: list[models.Bookmark],
    page: int = 1,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": f"{len(content_matrix)} 페이지 중에 {page} 페이지",
            },  # TODO: 프론트 링크 붙이기
        },
    )
    for content in content_matrix.get(page, []):
        if content.content_url:
            blocks.append({"type": "divider"})
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*<{content.content_url}|{re.sub('<|>', '', content.title)}>*",  # noqa E501
                    },
                    "accessory": {
                        "type": "overflow",
                        "action_id": "bookmark_overflow_action",
                        "options": [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "북마크 취소📌",
                                    "emoji": True,
                                },
                                "value": str(  # TODO: 일관된 형식으로 리팩터링 필요
                                    dict(
                                        action="remove_bookmark",
                                        content_id=content.content_id,
                                    )
                                ),
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "메모 보기✏️",
                                    "emoji": True,
                                },
                                "value": str(
                                    dict(
                                        action="view_note",
                                        content_id=content.content_id,
                                    )
                                ),
                            },
                        ],
                    },
                }
            )

            note = [
                bookmark.note
                for bookmark in bookmarks
                if content.content_id == bookmark.content_id
            ][0]

            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"\n> 메모: {note}"},
                    ],
                }
            )
        if len(blocks) > 60:
            return blocks
    return blocks


async def open_overflow_action(
    ack,
    body,
    client,
    view,
    say,
    user_id: str,
    service: SlackService,
) -> None:
    """북마크 메뉴 선택"""
    await ack()
    private_metadata = body["view"]["private_metadata"]

    title = ""
    text = ""
    value = ast.literal_eval(
        body["actions"][0]["selected_option"]["value"]
    )  # TODO: ast.literal_eval 를 유틸함수로 만들기?
    if value["action"] == "remove_bookmark":
        title = "북마크 취소📌"
        service.update_bookmark(
            user_id, value["content_id"], new_status=models.BookmarkStatusEnum.DELETED
        )
        text = "북마크를 취소했어요."
    elif value["action"] == "view_note":
        title = "북마크 메모✏️"
        bookmark = service.get_bookmark(user_id, value["content_id"])
        text = bookmark.note if bookmark and bookmark.note else "메모가 없어요."

    await client.views_update(
        view_id=body["view"]["id"],
        view={
            "type": "modal",
            "callback_id": "handle_bookmark_page_view",
            "private_metadata": private_metadata,
            "title": {
                "type": "plain_text",
                "text": title,
            },
            "submit": {"type": "plain_text", "text": "돌아가기"},
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": text},
                },
            ],
        },
    )


def _get_content_metrix(
    contents: list[models.Content],
) -> dict[int, list[models.Content]]:
    """컨텐츠를 2차원 배열로 변환합니다."""
    content_matrix = {}
    for i, v in enumerate(range(0, len(contents), CONTENTS_PER_PAGE)):
        content_matrix.update({i + 1: contents[v : v + CONTENTS_PER_PAGE]})
    return content_matrix


# TODO: 니즈가 확인되는 경우 활성화
# async def bookmark_search_view(
#     ack, body, say, client, user_id: str, service: SlackService,
# ) -> None:
#     """북마크 검색 시작"""
#     view = {
#         "type": "modal",
#         "callback_id": "bookmark_submit_search_view",
#         "title": {"type": "plain_text", "text": "북마크 검색 🔍"},
#         "submit": {"type": "plain_text", "text": "검색"},
#         "blocks": [
#             {
#                 "type": "section",
#                 "block_id": "description_section",
#                 "text": {
#                     "type": "mrkdwn",
#                     "text": "찾고 있는 북마크가 있나요?\n키워드로 연관된 글을 찾을 수 있어요!",
#                 },
#             },
#             {
#                 "type": "input",
#                 "block_id": "keyword_search",
#                 "optional": True,
#                 "element": {
#                     "type": "plain_text_input",
#                     "action_id": "keyword",
#                     "placeholder": {
#                         "type": "plain_text",
#                         "text": "키워드를 입력해주세요.",
#                     },
#                     "multiline": False,
#                 },
#                 "label": {
#                     "type": "plain_text",
#                     "text": "키워드",
#                     "emoji": True,
#                 },
#             },
#         ],
#     }

#     await ack({"response_action": "update", "view": view})

# TODO: 니즈가 확인되는 경우 활성화
# async def bookmark_submit_search_view(
#     ack, body, say, client, user_id: str, service: SlackService
# ) -> None:
#     """북마크 검색 완료"""
#     keyword = _get_keyword(body)
#     bookmarks = service.fetch_bookmarks(user_id)

#     ids = [bookmark.content_id for bookmark in bookmarks if keyword in bookmark.note]
#     contents_with_keyword_in_notes = service.fetch_contents_by_ids(ids)

#     ids = [bookmark.content_id for bookmark in bookmarks]
#     contents_with_keyword = service.fetch_contents_by_ids(ids, keyword)

#     contents = list(set(contents_with_keyword_in_notes + contents_with_keyword))
#     content_matrix = _get_content_metrix(contents)

#     await ack(
#         {
#             "response_action": "update",
#             "view": {
#                 "type": "modal",
#                 "callback_id": "bookmark_search_view",
#                 "title": {
#                     "type": "plain_text",
#                     "text": f"{len(contents)} 개의 북마크를 찾았어요.",
#                 },
#                 "submit": {"type": "plain_text", "text": "북마크 검색"},
#                 "blocks": _fetch_bookmark_blocks(content_matrix, bookmarks),
#             },
#         }
#     )
