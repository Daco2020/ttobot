from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from typing import Any

from app.slack.services import SlackService
import csv
import re


async def trigger_command(
    ack, body, say, client: AsyncWebClient, user_id: str, service: SlackService
) -> None:
    """저장할 키워드 등록 시작"""
    await ack()

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "private_metadata": body["channel_id"],
            "callback_id": "trigger_view",
            "title": {"type": "plain_text", "text": "저장할 키워드 등록"},
            "submit": {"type": "plain_text", "text": "등록"},
            "blocks": [
                {
                    "type": "section",
                    "block_id": "description_section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"키워드를 등록하면 <#{body['channel_id']}> 에서 키워드가 포함된 메시지를 저장할 수 있어요. 😉",  # noqa E501
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
                        "text": "'$'으로 시작하는 키워드를 입력해주세요. \n예) $회고, $기록, $메모, ...",
                        "emoji": True,
                    },
                },
            ],
        },
    )


async def trigger_view(ack, body, client, view, say, user_id: str, service: SlackService) -> None:
    """저장할 키워드 등록"""
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
        error_message = "키워드는 $으로 시작해주세요."
    elif len(trigger_word) <= 1:
        error_message = "키워드는 두글자 이상으로 만들어주세요."
    elif " " in trigger_word:
        error_message = "키워드는 공백을 사용할 수 없어요."
    elif is_similar_word:
        error_message = f"이미 유사한 키워드가 존재해요. {','.join(existing_trigger_words)} 과(와) 구별되는 키워드를 입력해주세요."  # noqa E501

    if error_message:
        await ack(
            response_action="errors",
            errors={"trigger_word": error_message},
        )
        raise ValueError(error_message)

    service.create_trigger_message(user_id, channel_id, trigger_word)

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {"type": "plain_text", "text": "키워드 등록 완료🥳"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"이제 <#{channel_id}> 채널에서 `{trigger_word}` 키워드가 포함된 메시지를 저장합니다. 😉",  # noqa E501
                    },
                }
            ],
        },
    )


async def handle_trigger_message(
    client: AsyncWebClient,
    event: dict[str, Any],
    service: SlackService,
) -> None:
    channel_id = event["channel"]
    is_message_changed = False

    if event.get("subtype") == "message_changed":
        is_message_changed = True
        message_changed_ts = event["event_ts"]
        event = event["message"]  # 메시지 수정 이벤트는 event["message"]안에 있습니다.

        # 슬랙은 미리보기를 message_changed 이벤트로 생성하는데, 이 경우 동작하지 않도록 합니다.
        # 7초 이내에 수정된 메시지는 미리보기 생성으로 판단합니다.
        time_difference = float(message_changed_ts) - float(event["ts"])
        if 0 <= time_difference <= 7:
            return None

    elif event.get("subtype") == "file_share":
        pass
    elif event.get("subtype"):
        # 수정/파일공유 외 메시지는 저장하지 않습니다.
        return None

    message = event["text"]
    ts = event["ts"]
    user_id = event["user"]
    files = event.get("files")
    file_urls = [file.get("url_private") for file in files] if files else []

    trigger = service.get_trigger_message(channel_id, message)
    if not trigger:
        return None

    message = convert_user_id_to_name(message)

    if is_message_changed:
        is_created = service.update_archive_message(
            ts=ts,
            channel_id=channel_id,
            message=message,
            user_id=user_id,
            trigger_word=trigger.trigger_word,
            file_urls=file_urls,
        )
    else:
        is_created = True
        service.create_archive_message(
            ts=ts,
            channel_id=channel_id,
            message=message,
            user_id=user_id,
            trigger_word=trigger.trigger_word,
            file_urls=file_urls,
        )
    try:
        await client.reactions_add(
            channel=channel_id,
            timestamp=ts,
            name="round_pushpin",
        )
    except SlackApiError as e:
        if e.response["error"] == "already_reacted":
            # 이미 이모지 반응을 한 경우 패스합니다.
            pass

    archive_messages = service.fetch_archive_messages(channel_id, trigger.trigger_word, user_id)

    if is_created:  # 새로운 메시지 or 기존 메시지에 트리거 단어를 추가한 메시지
        response_message = f"<@{user_id}>님의 {len(archive_messages)}번째 `{trigger.trigger_word}` 메시지를 저장했어요. 😉"
    else:
        response_message = f"<@{user_id}>님의 `{trigger.trigger_word}` 메시지를 수정했어요. 😉"

    await client.chat_postMessage(
        channel=channel_id,
        thread_ts=ts,
        text=response_message,
    )


def convert_user_id_to_name(message: str) -> str:
    """메시지에서 user_id를 name으로 변경합니다."""
    with open("store/users.csv") as f:
        reader = csv.DictReader(f)
        user_dict = {row["user_id"]: row["name"] for row in reader}

    user_ids = re.findall("<@([A-Z0-9]+)>", message)

    for user_id in user_ids:
        name = user_dict.get(user_id, user_id)
        message = message.replace(f"<@{user_id}>", name)

    return message
