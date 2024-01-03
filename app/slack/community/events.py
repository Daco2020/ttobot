from collections import namedtuple
from slack_sdk.web.async_client import AsyncWebClient

from typing import Any


MessageTrigger = namedtuple(
    "MessageTrigger", ["channel_id", "trigger_word", "reaction_emoji", "answer"]
)


async def handle_message_trigger(
    client: AsyncWebClient,
    event: dict[str, Any],
) -> None:
    message_triggers = [
        MessageTrigger(
            channel_id="C05JDJF16MA",
            trigger_word="#감사",
            reaction_emoji="four_leaf_clover",
            answer="감사합니다.",
        ),
        MessageTrigger(
            channel_id="C05JDJF16MA",
            trigger_word="#회고",
            reaction_emoji="four_leaf_clover",
            answer="감사합니다.",
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
