from typing import Any, TypedDict

from app.slack.components.types import (
    DatePickerAccessory,
    MrkdwnText,
    PlainText,
    SectionButtonAccessory,
    SectionCheckboxAccessory,
    SectionLinkButtonAccessory,
    SectionMrkdwnText,
    SectionMultiConversationsSelectAccessory,
    SectionMultiStaticSelectAccessory,
    SectionPlainText,
    SectionRadioButtonsAccessory,
    SectionStaticSelectAccessory,
    SectionUsersSelectAccessory,
    TimePickerAccessory,
)


def section(
    *,
    text: PlainText | MrkdwnText,
    accessory: dict[str, Any] | None = None,
) -> Any:
    """
    섹션 블록을 생성합니다.

    text:
    - PlainText
    - MrkdwnText

    accessory:
    - UsersSelectAccessory
    - StaticSelectAccessory
    - MultiStaticSelectAccessory
    - MultiConversationsSelectAccessory
    - ButtonAccessory
    - LinkButtonAccessory
    - ImageAccessory
    - SlackImageAccessory
    - OverflowAccessory
    - CheckboxAccessory
    - RadioButtonsAccessory
    - DatePickerAccessory
    - TimePickerAccessory
    """
    section = {
        "type": "section",
        "text": text,
    }
    section.update(accessory) if accessory else None
    return section


def plain_text(
    *,
    text: str,
) -> SectionPlainText:
    """
    # Example
    {
        "type": "section",
        "text": { <-- This is the text block
            "type": "plain_text",
            "text": "This is a section block with a button.",
            "emoji": True,
        },
    }
    """
    return section(
        text={
            "type": "plain_text",
            "text": text,
            "emoji": True,
        }
    )


def mrkdwn_text(
    *,
    text: str,
) -> SectionMrkdwnText:
    """
    # Example
    {
        "type": "section",
        "text": { <-- This is the text block
            "type": "mrkdwn",
            "text": "This is a section block with a button.",
        },
    }
    """
    return section(
        text={
            "type": "mrkdwn",
            "text": text,
        }
    )


def users_select_accessory(
    *,
    text: PlainText | MrkdwnText,
    placeholder_text: str,
    action_id: str,
) -> SectionUsersSelectAccessory:
    """
    # Example
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "Test block with users select"},
        "accessory": { <-- This is the accessory block
            "type": "users_select",
            "placeholder": {"type": "plain_text", "text": "Select a user", "emoji": True},
            "action_id": "users_select-action",
        },
    }
    """
    return section(
        text=text,
        accessory={
            "type": "users_select",
            "placeholder": {
                "type": "plain_text",
                "text": placeholder_text,
                "emoji": True,
            },
            "action_id": action_id,
        },
    )


def static_select_accessory(
    *,
    text: PlainText | MrkdwnText,
    placeholder_text: str,
    options: list[dict[str, Any]],
    action_id: str,
) -> SectionStaticSelectAccessory:
    """
    # Example
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "Pick an item from the dropdown list"},
        "accessory": { <-- This is the accessory block
            "type": "static_select",
            "placeholder": {"type": "plain_text", "text": "Select an item", "emoji": True},
            "options": [
                {
                    "text": {
                        "type": "plain_text",
                        "text": "*plain_text option 0*",
                        "emoji": True,
                    },
                    "value": "value-0",
                },
                {
                    "text": {
                        "type": "plain_text",
                        "text": "*plain_text option 1*",
                        "emoji": True,
                    },
                    "value": "value-1",
                },
                {
                    "text": {
                        "type": "plain_text",
                        "text": "*plain_text option 2*",
                        "emoji": True,
                    },
                    "value": "value-2",
                },
            ],
            "action_id": "static_select-action",
        },
    }
    """
    return section(
        text=text,
        accessory={
            "type": "static_select",
            "placeholder": {
                "type": "plain_text",
                "text": placeholder_text,
                "emoji": True,
            },
            "options": options,
            "action_id": action_id,
        },
    )


def multi_static_select_accessory(
    *,
    text: PlainText | MrkdwnText,
    placeholder_text: str,
    options: list[dict[str, Any]],
    action_id: str,
) -> SectionMultiStaticSelectAccessory:
    """
    # Example
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "Test block with multi static select"},
        "accessory": { <- This is the accessory block
            "type": "multi_static_select",
            "placeholder": {"type": "plain_text", "text": "Select options", "emoji": True},
            "options": [
                {
                    "text": {
                        "type": "plain_text",
                        "text": "*plain_text option 0*",
                        "emoji": True,
                    },
                    "value": "value-0",
                },
                {
                    "text": {
                        "type": "plain_text",
                        "text": "*plain_text option 1*",
                        "emoji": True,
                    },
                    "value": "value-1",
                },
                {
                    "text": {
                        "type": "plain_text",
                        "text": "*plain_text option 2*",
                        "emoji": True,
                    },
                    "value": "value-2",
                },
            ],
            "action_id": "multi_static_select-action",
        },
    }
    """
    return section(
        text=text,
        accessory={
            "type": "multi_static_select",
            "placeholder": {
                "type": "plain_text",
                "text": placeholder_text,
                "emoji": True,
            },
            "options": options,
            "action_id": action_id,
        },
    )


def multi_conversations_select_accessory(
    *,
    text: PlainText | MrkdwnText,
    placeholder_text: str,
    action_id: str,
) -> SectionMultiConversationsSelectAccessory:
    """
    # Example
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "Test block with multi conversations select"},
        "accessory": { <- This is the accessory block
            "type": "multi_conversations_select",
            "placeholder": {
                "type": "plain_text",
                "text": "Select conversations",
                "emoji": True,
            },
            "action_id": "multi_conversations_select-action",
        },
    }
    """
    return section(
        text=text,
        accessory={
            "type": "multi_conversations_select",
            "placeholder": {
                "type": "plain_text",
                "text": placeholder_text,
                "emoji": True,
            },
            "action_id": action_id,
        },
    )


def button_accessory(
    *,
    text: PlainText | MrkdwnText,
    button_text: str,
    value: str,
    action_id: str,
) -> SectionButtonAccessory:
    """
    # Example
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "This is a section block with a button."},
        "accessory": { <- This is the accessory block
            "type": "button",
            "text": {"type": "plain_text", "text": "Click Me", "emoji": True},
            "value": "click_me_123",
            "action_id": "button-action",
        },
    }
    """
    return section(
        text=text,
        accessory={
            "type": "button",
            "text": {"type": "plain_text", "text": button_text, "emoji": True},
            "value": value,
            "action_id": action_id,
        },
    )


def link_button_accessory(
    *,
    text: PlainText | MrkdwnText,
    button_text: str,
    value: str,
    url: str,
    action_id: str,
) -> SectionLinkButtonAccessory:
    """
    # Example
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "This is a section block with a button."},
        "accessory": { <- This is the accessory block
            "type": "button",
            "text": {"type": "plain_text", "text": "Click Me", "emoji": True},
            "value": "click_me_123",
            "url": "https://google.com",
            "action_id": "button-action",
        },
    }
    """
    return section(
        text=text,
        accessory={
            "type": "button",
            "text": {"type": "plain_text", "text": button_text, "emoji": True},
            "value": value,
            "url": url,
            "action_id": action_id,
        },
    )


class ImageAccessory(TypedDict):
    type: str
    image_url: str
    alt_text: str


class SectionImageAccessory(TypedDict):
    type: str
    text: PlainText | MrkdwnText
    accessory: ImageAccessory


def image_accessory(
    *,
    text: PlainText | MrkdwnText,
    image_url: str,
    alt_text: str,
) -> SectionImageAccessory:
    """
    # Example
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "This is a section block with an accessory image.",
        },
        "accessory": { <- This is the accessory block
            "type": "image",
            "image_url": "https://pbs.twimg.com/profile_images/625633822235693056/lNGUneLX_400x400.jpg",
            "alt_text": "cute cat",
        },
    }
    """
    return section(
        text=text,
        accessory={
            "type": "image",
            "image_url": image_url,
            "alt_text": alt_text,
        },
    )


class SlackImageAccessory(TypedDict):
    type: str
    slack_file: dict[str, Any]
    alt_text: str


class SectionSlackImageAccessory(TypedDict):
    type: str
    text: PlainText | MrkdwnText
    accessory: SlackImageAccessory


def slack_image_accessory(
    *,
    text: PlainText | MrkdwnText,
    slack_file: dict[str, Any],
    alt_text: str,
) -> SectionSlackImageAccessory:
    """
    # Example
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "This is a section block with an accessory image.",
        },
        "accessory": { <- This is the accessory block
            "type": "image",
            "slack_file": {"url": "<insert slack file url here>"},
            "alt_text": "alt text",
        },
    }
    """
    return section(
        text=text,
        accessory={
            "type": "image",
            "slack_file": {"url": slack_file},
            "alt_text": alt_text,
        },
    )


class OverflowAccessory(TypedDict):
    type: str
    options: list[dict[str, Any]]
    action_id: str


class SectionOverflowAccessory(TypedDict):
    type: str
    text: PlainText | MrkdwnText
    accessory: OverflowAccessory


def overflow_accessory(
    *,
    text: PlainText | MrkdwnText,
    options: list[dict[str, Any]],
    action_id: str,
) -> SectionOverflowAccessory:
    """
    # Example
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "This is a section block with an overflow menu.",
        },
        "accessory": { <- This is the accessory block
            "type": "overflow",
            "options": [
                {
                    "text": {
                        "type": "plain_text",
                        "text": "*plain_text option 0*",
                        "emoji": True,
                    },
                    "value": "value-0",
                },
                {
                    "text": {
                        "type": "plain_text",
                        "text": "*plain_text option 1*",
                        "emoji": True,
                    },
                    "value": "value-1",
                },
                {
                    "text": {
                        "type": "plain_text",
                        "text": "*plain_text option 2*",
                        "emoji": True,
                    },
                    "value": "value-2",
                },
            ],
            "action_id": "overflow-action",
        },
    }
    """
    return section(
        text=text,
        accessory={
            "type": "overflow",
            "options": options,
            "action_id": action_id,
        },
    )


def checkbox_accessory(
    *,
    text: PlainText | MrkdwnText,
    options: list[dict[str, Any]],
    action_id: str,
) -> SectionCheckboxAccessory:
    """
    # Example
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "This is a section block with checkboxes."},
        "accessory": { <- This is the accessory block
            "type": "checkboxes",
            "options": [
                {
                    "text": {"type": "mrkdwn", "text": "*this is mrkdwn text*"},
                    "description": {"type": "mrkdwn", "text": "*this is mrkdwn text*"},
                    "value": "value-0",
                },
                {
                    "text": {"type": "mrkdwn", "text": "*this is mrkdwn text*"},
                    "description": {"type": "mrkdwn", "text": "*this is mrkdwn text*"},
                    "value": "value-1",
                },
                {
                    "text": {"type": "mrkdwn", "text": "*this is mrkdwn text*"},
                    "description": {"type": "mrkdwn", "text": "*this is mrkdwn text*"},
                    "value": "value-2",
                },
            ],
            "action_id": "checkboxes-action",
        },
    }
    """
    return section(
        text=text,
        accessory={
            "type": "checkboxes",
            "options": options,
            "action_id": action_id,
        },
    )


def radio_buttons_accessory(
    *,
    text: PlainText | MrkdwnText,
    options: list[dict[str, Any]],
    action_id: str,
) -> SectionRadioButtonsAccessory:
    """
    # Example
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "Section block with radio buttons"},
        "accessory": { <- This is the accessory block
            "type": "radio_buttons",
            "options": [
                {
                    "text": {
                        "type": "plain_text",
                        "text": "*plain_text option 0*",
                        "emoji": True,
                    },
                    "value": "value-0",
                },
                {
                    "text": {
                        "type": "plain_text",
                        "text": "*plain_text option 1*",
                        "emoji": True,
                    },
                    "value": "value-1",
                },
                {
                    "text": {
                        "type": "plain_text",
                        "text": "*plain_text option 2*",
                        "emoji": True,
                    },
                    "value": "value-2",
                },
            ],
            "action_id": "radio_buttons-action",
        },
    }
    """
    return section(
        text=text,
        accessory={
            "type": "radio_buttons",
            "options": options,
            "action_id": action_id,
        },
    )


def date_picker_accessory(
    *,
    text: PlainText | MrkdwnText,
    initial_date: str,
    placeholder_text: str,
    action_id: str,
) -> DatePickerAccessory:
    """
    # Example
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "Pick a date for the deadline."},
        "accessory": { <- This is the accessory block
            "type": "datepicker",
            "initial_date": "1990-04-28",
            "placeholder": {
                "type": "plain_text",
                "text": "Select a date",
                "emoji": True,
            },
            "action_id": "datepicker-action",
        },
    }
    """
    return section(
        text=text,
        accessory={
            "type": "datepicker",
            "initial_date": initial_date,
            "placeholder": {
                "type": "plain_text",
                "text": placeholder_text,
                "emoji": True,
            },
            "action_id": action_id,
        },
    )


def time_picker_accessory(
    *,
    text: PlainText | MrkdwnText,
    initial_time: str,
    placeholder_text: str,
    action_id: str,
) -> TimePickerAccessory:
    """
    # Example
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "Section block with a timepicker"},
        "accessory": { <- This is the accessory block
            "type": "timepicker",
            "initial_time": "13:37",
            "placeholder": {
                "type": "plain_text",
                "text": "Select time",
                "emoji": True,
            },
            "action_id": "timepicker-action",
        },
    }
    """
    return section(
        text=text,
        accessory={
            "type": "timepicker",
            "initial_time": initial_time,
            "placeholder": {
                "type": "plain_text",
                "text": placeholder_text,
                "emoji": True,
            },
            "action_id": action_id,
        },
    )
