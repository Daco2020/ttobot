from slack_sdk.web.async_client import AsyncWebClient

from typing import Any

from app.slack.services import SlackService
import csv
import re


async def trigger_command(
    ack, body, say, client: AsyncWebClient, user_id: str, service: SlackService
) -> None:
    """메시지 트리거 등록"""
    await ack()

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "private_metadata": body["channel_id"],
            "callback_id": "trigger_view",
            "title": {"type": "plain_text", "text": "메시지 트리거 등록"},
            "submit": {"type": "plain_text", "text": "등록"},
            "blocks": [
                {
                    "type": "section",
                    "block_id": "description_section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"메시지 트리거를 등록하면 <#{body['channel_id']}> 에서 트리거가 포함된 메시지를 저장할 수 있어요. 😉",
                    },
                },
                {
                    "type": "input",
                    "block_id": "trigger_word",
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
                        "text": "'$'으로 시작하는 트리거 단어를 입력해주세요. \n예) $회고, $기록, $메모, ...",
                        "emoji": True,
                    },
                },
            ],
        },
    )


async def trigger_view(
    ack, body, client, view, say, user_id: str, service: SlackService
) -> None:
    """메시지 트리거 생성"""
    await ack()

    user_id = body["user"]["id"]
    channel_id = view["private_metadata"]
    trigger_word = view["state"]["values"]["trigger_word"]["trigger_word"]["value"]

    triggers = service.fetch_trigger_messages(channel_id)
    existing_trigger_words = [trigger.trigger_word for trigger in triggers]

    is_similar_word = [
        each for each in existing_trigger_words if each in trigger_word
    ] or trigger_word in ",".join(existing_trigger_words)

    error_message = ""
    if trigger_word[0] != "$":
        error_message = "트리거 단어는 $으로 시작해주세요."
    elif len(trigger_word) <= 1:
        error_message = "트리거 단어는 두글자 이상으로 만들어주세요."
    elif " " in trigger_word:
        error_message = "트리거 단어는 공백을 사용할 수 없어요."
    elif is_similar_word:
        error_message = f"이미 유사한 트리거 단어가 존재해요. {','.join(existing_trigger_words)} 과(와) 구별되는 트리거 단어를 입력해주세요."

    if error_message:
        await ack(
            response_action="errors",
            errors={"trigger_word": error_message},
        )
        raise ValueError(error_message)

    service.create_trigger_message(user_id, channel_id, trigger_word)


async def handle_trigger_message(
    client: AsyncWebClient,
    event: dict[str, Any],
    service: SlackService,
) -> None:
    ts = event["ts"]
    channel_id = event["channel"]
    message = event["text"]
    user_id = event["user"]
    files = event.get("files")
    file_urls = [file.get("url_private") for file in files] if files else []

    trigger = service.get_trigger_message(channel_id, message)
    if not trigger:
        return None

    # user_id를 name으로 변경
    with open("store/users.csv") as f:
        reader = csv.DictReader(f)
        user_dict = {row["user_id"]: row["name"] for row in reader}

    user_ids = re.findall("<@([A-Z0-9]+)>", message)
    for user_id in user_ids:
        name = user_dict.get(user_id, user_id)
        message = message.replace(f"<@{user_id}>", name)

    service.create_archive_message(
        ts=ts,
        channel_id=channel_id,
        message=message,
        user_id=user_id,
        trigger_word=trigger.trigger_word,
        file_urls=file_urls,
    )
    await client.reactions_add(
        channel=channel_id,
        timestamp=ts,
        name="round_pushpin",
    )

    archive_messages = service.fetch_archive_messages(
        channel_id, trigger.trigger_word, user_id
    )

    response_message = f"<@{user_id}>님의 {len(archive_messages)}번째 `{trigger.trigger_word}` 메시지를 저장했어요. 😉"
    await client.chat_postMessage(
        channel=channel_id,
        thread_ts=ts,
        text=response_message,
    )
