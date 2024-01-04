from collections import namedtuple
from slack_sdk.web.async_client import AsyncWebClient

from typing import Any

from app.slack.services import SlackService


async def trigger_command(
    ack, body, say, client: AsyncWebClient, user_id: str, service: SlackService
) -> None:
    """트리거 설정"""
    await ack()

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "private_metadata": body["channel_id"],
            "callback_id": "trigger_view",
            "title": {"type": "plain_text", "text": "트리거 설정"},
            "submit": {"type": "plain_text", "text": "트리거 등록"},
            "blocks": [
                {
                    "type": "section",
                    "block_id": "description_section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "트리거 단어를 등록하면 특정 메시지를 따로 저장할 수 있어요.",
                    },
                },
                {
                    "type": "input",
                    "block_id": "trigger_word",
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "trigger_word",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "예) $회고, $기록, $메모, ...",
                        },
                        "multiline": False,
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "'$'으로 시작하는 트리거 단어를 입력해주세요. 예) '$기록'",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "트리거를 적용할 채널을 선택해주세요.",
                    },
                    "accessory": {
                        "type": "conversations_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "채널 선택",
                            "emoji": True,
                        },
                        "filter": {
                            "include": ["public"],
                            "exclude_bot_users": True,
                        },
                        "action_id": "trigger_view_channel_select",
                    },
                },
            ],
        },
    )


async def trigger_view(
    ack, body, client, view, say, user_id: str, service: SlackService
) -> None:
    """트리거 메시지 생성"""
    await ack()

    user_id = body["user"]["id"]
    channel_id = view["private_metadata"]
    trigger_word = view["state"]["values"]["trigger_word"]["trigger_word"]["value"]

    if trigger_word and "$" != trigger_word[0]:
        await ack(
            response_action="errors",
            errors={
                "trigger_word": "트리거 단어는 #으로 시작해야 합니다.",
            },
        )
        raise ValueError("트리거 단어는 #으로 시작해야 합니다.")

    service.create_trigger_message(user_id, channel_id, trigger_word)


TriggerMessage = namedtuple("TriggerMessage", ["channel_id", "trigger_word"])


async def handle_message_trigger(
    client: AsyncWebClient,
    event: dict[str, Any],
) -> None:
    message_triggers = [
        TriggerMessage(
            channel_id="C05JDJF16MA",
            trigger_word="#감사",
        ),
        TriggerMessage(
            channel_id="C05JDJF16MA",
            trigger_word="#회고",
        ),
    ]
    for trigger in message_triggers:
        files = event.get("files")

        ts = event["ts"]
        channel_id = event["channel"]
        message = event["text"]
        user_id = event["user"]
        if files:
            file_urls = [file.get("url_private") for file in files]

        if channel_id == trigger.channel_id and trigger.trigger_word in message:
            await client.reactions_add(
                channel=channel_id,
                timestamp=ts,
                name="four_leaf_clover",
            )
            break
