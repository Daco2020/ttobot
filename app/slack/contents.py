import ast
import re
from typing import Any

import loguru
from app import models
from app.config import ANIMAL_TYPE, PASS_VIEW, SUBMIT_VIEW
from app.services import user_content_service
from app.logging import event_log


async def submit_command(ack, body, logger, say, client, user_id: str) -> None:
    event_log(user_id, event="글 제출 시작")
    await ack()

    await user_content_service.open_submit_modal(body, client, SUBMIT_VIEW)


async def submit_view(ack, body, client, view, logger, say, user_id: str) -> None:
    event_log(user_id, event="글 제출 완료")
    await ack()

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
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text,
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "자기소개 보기"},
                            "action_id": "intro_modal",
                            "value": user.user_id,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "이전 작성글 보기"},
                            "action_id": "contents_modal",
                            "value": user.user_id,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "북마크 추가📌"},
                            "action_id": "bookmark_modal",
                            "value": content.unique_id,
                        },
                    ],
                },
            ],
        )
    except Exception as e:
        message = f"{user.name}({user.channel_name}) 님의 제출이 실패하였습니다. {str(e)}"
        loguru.logger.error(message)  # TODO: 디스코드 알림 보내기


async def open_intro_modal(ack, body, client, view, logger, user_id: str) -> None:
    event_log(user_id, event="다른 유저의 자기소개 확인")
    await ack()

    target_user_id = body["actions"][0]["value"]
    user = user_content_service.get_user_not_valid(target_user_id)
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


async def contents_modal(ack, body, client, view, logger, user_id: str) -> None:
    event_log(user_id, event="다른 유저의 제출한 글 목록 확인")
    await ack()

    target_user_id = body["actions"][0]["value"]
    user = user_content_service.get_user_not_valid(target_user_id)

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {"type": "plain_text", "text": f"{user.name}님의 작성글"},
            "close": {"type": "plain_text", "text": "닫기"},
            "blocks": _fetch_blocks(user.contents),
        },
    )


async def bookmark_modal(ack, body, client, view, logger, user_id: str) -> None:
    event_log(user_id, event="북마크 저장 시작")
    await ack()

    actions = body["actions"][0]
    is_overflow = actions["type"] == "overflow"  # TODO: 분리필요
    if is_overflow:
        content_id = actions["selected_option"]["value"]
    else:
        content_id = actions["value"]

    bookmark = user_content_service.get_bookmark(user_id, content_id)
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
                    "text": {"type": "mrkdwn", "text": "\n이미 북마크한 글입니다. 😉"},
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
                        "text": "\n북마크한 글은 `/북마크` 명령어로 다시 확인할 수 있습니다.",
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


async def bookmark_view(ack, body, client, view, logger, say, user_id: str) -> None:
    event_log(user_id, event="북마크 저장 완료")

    await ack()

    content_id = view["private_metadata"]
    value = view["state"]["values"]["bookmark_note"]["plain_text_input-action"]["value"]
    note = value if value else ""  # 유저가 입력하지 않으면 None 으로 전달 된다.
    user_content_service.create_bookmark(user_id, content_id, note)

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
                        "text": {"type": "mrkdwn", "text": "\n북마크를 추가했습니다.😉"},
                    }
                ],
            },
        }
    )


async def pass_command(ack, body, logger, say, client, user_id: str) -> None:
    event_log(user_id, event="글 패스 시작")
    await ack()

    await user_content_service.open_pass_modal(body, client, PASS_VIEW)


async def pass_view(ack, body, client, view, logger, say, user_id: str) -> None:
    event_log(user_id, event="글 패스 완료")
    await ack()

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
        message = f"{user.name}({user.channel_name}) 님의 패스가 실패하였습니다. {str(e)}"
        loguru.logger.error(message)  # TODO: 디스코드 알림 보내기


async def search_command(ack, body, logger, say, client, user_id: str) -> None:
    event_log(user_id, event="글 검색 시작")
    await ack()

    await user_content_service.open_search_modal(body, client)


async def submit_search(ack, body, client, view, logger, user_id: str):
    event_log(user_id, event="글 검색 완료")

    name = _get_name(body)
    category = _get_category(body)
    keyword = _get_keyword(body)

    contents = user_content_service.fetch_contents(keyword, name, category)

    await ack(
        {
            "response_action": "update",
            "view": {
                "type": "modal",
                "callback_id": "back_to_search_view",
                "title": {
                    "type": "plain_text",
                    "text": f"총 {len(contents)} 개의 글이 있습니다. 🔍",
                },
                "submit": {"type": "plain_text", "text": "다시 찾기"},
                "blocks": _fetch_blocks(contents),
            },
        }
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
                                "value": content.unique_id,
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


async def back_to_search_view(ack, body, logger, say, client, user_id: str) -> None:
    event_log(user_id, event="글 검색 다시 시작")

    view = {
        "type": "modal",
        "callback_id": "submit_search",
        "title": {"type": "plain_text", "text": "글 검색 🔍"},
        "submit": {"type": "plain_text", "text": "찾기"},
        "blocks": [
            {
                "type": "section",
                "block_id": "description_section",
                "text": {"type": "mrkdwn", "text": "조건에 맞는 글을 검색합니다."},
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
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "전체"},
                            "value": "전체",
                        },
                        {
                            "text": {"type": "plain_text", "text": "프로젝트"},
                            "value": "프로젝트",
                        },
                        {
                            "text": {"type": "plain_text", "text": "기술 & 언어"},
                            "value": "기술 & 언어",
                        },
                        {
                            "text": {"type": "plain_text", "text": "조직 & 문화"},
                            "value": "조직 & 문화",
                        },
                        {
                            "text": {"type": "plain_text", "text": "취준 & 이직"},
                            "value": "취준 & 이직",
                        },
                        {
                            "text": {"type": "plain_text", "text": "일상 & 생각"},
                            "value": "일상 & 생각",
                        },
                        {
                            "text": {"type": "plain_text", "text": "기타"},
                            "value": "기타",
                        },
                    ],
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


async def bookmark_command(ack, body, logger, say, client, user_id: str) -> None:
    event_log(user_id, event="북마크 조회")
    await ack()

    bookmarks = user_content_service.fetch_bookmarks(user_id)
    content_ids = [bookmark.content_id for bookmark in bookmarks]
    contents = user_content_service.fetch_contents_by_ids(content_ids)

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "bookmark_search_view",
            "title": {
                "type": "plain_text",
                "text": f"총 {len(contents)} 개의 북마크가 있습니다.",
            },
            "submit": {"type": "plain_text", "text": "북마크 검색"},
            "blocks": _fetch_bookmark_blocks(contents),
        },
    )


def _fetch_bookmark_blocks(contents: list[models.Content]) -> list[dict[str, Any]]:
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
                                        content_id=content.unique_id,
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
                                        content_id=content.unique_id,
                                    )
                                ),
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


async def bookmark_search_view(ack, body, logger, say, client, user_id: str) -> None:
    event_log(user_id, event="북마크 검색 시작")

    view = {
        "type": "modal",
        "callback_id": "bookmark_submit_search_view",
        "title": {"type": "plain_text", "text": "북마크 검색 🔍"},
        "submit": {"type": "plain_text", "text": "검색"},
        "blocks": [
            {
                "type": "section",
                "block_id": "description_section",
                "text": {
                    "type": "mrkdwn",
                    "text": "찾고 있는 북마크가 있나요?\n키워드를 입력하면 쉽게 찾을 수 있어요!",
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
        ],
    }

    await ack({"response_action": "update", "view": view})


async def open_overflow_action(
    ack, body, client, view, logger, say, user_id: str
) -> None:
    event_log(user_id, event="북마크 메뉴 선택")
    await ack()

    title = ""
    text = ""
    value = ast.literal_eval(body["actions"][0]["selected_option"]["value"])
    if value["action"] == "remove_bookmark":
        title = "북마크 취소📌"
        user_content_service.update_bookmark(
            value["content_id"], new_status=models.BookmarkStatusEnum.DELETED
        )
        text = "북마크를 취소하였습니다."
    elif value["action"] == "view_note":
        title = "북마크 메모✏️"
        bookmark = user_content_service.get_bookmark(user_id, value["content_id"])
        text = bookmark.note if bookmark and bookmark.note else "메모가 없습니다."

    await client.views_update(
        view_id=body["view"]["id"],
        view={
            "type": "modal",
            "callback_id": "bookmark_submit_search_view",  # TODO: 액션에 따라 동적으로 호출
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


async def bookmark_submit_search_view(
    ack, body, logger, say, client, user_id: str
) -> None:
    event_log(user_id, event="북마크 검색 완료")

    keyword = _get_keyword(body)
    bookmarks = user_content_service.fetch_bookmarks(user_id)
    content_ids = [bookmark.content_id for bookmark in bookmarks]
    contents = user_content_service.fetch_contents_by_ids(content_ids, keyword)

    await ack(
        {
            "response_action": "update",
            "view": {
                "type": "modal",
                "callback_id": "bookmark_search_view",
                "title": {
                    "type": "plain_text",
                    "text": f"{len(contents)} 개의 북마크를 찾았습니다.",
                },
                "submit": {"type": "plain_text", "text": "북마크 검색"},
                "blocks": _fetch_bookmark_blocks(contents),
            },
        }
    )
