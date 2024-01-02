from collections import namedtuple
from slack_sdk.web.async_client import AsyncWebClient

from typing import Any


MessageTrigger = namedtuple(
    "MessageTrigger", ["channel_id", "trigger_word", "reaction_emoji", "answer"]
)


async def handle_message_trigger(
    client: AsyncWebClient,
    event: dict[str, Any],
    user_id: str,
    channel_id: str,
    thread_ts: str | None,
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
        if channel_id == trigger.channel_id and trigger.trigger_word in event["text"]:
            await client.reactions_add(
                channel=channel_id,
                timestamp=event["ts"],
                name="four_leaf_clover",
            )
            break
