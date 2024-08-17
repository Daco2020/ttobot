from typing import Any, TypedDict


class PlainText(TypedDict):
    type: str
    text: str
    emoji: bool


class SectionPlainText(TypedDict):
    type: str
    text: PlainText


class MrkdwnText(TypedDict):
    type: str
    text: str


class SectionMrkdwnText(TypedDict):
    type: str
    text: MrkdwnText


class UsersSelectAccessory(TypedDict):
    type: str
    placeholder: dict[str, Any]
    action_id: str


class SectionUsersSelectAccessory(TypedDict):
    type: str
    text: PlainText | MrkdwnText
    accessory: UsersSelectAccessory


class StaticSelectAccessory(TypedDict):
    type: str
    placeholder: dict[str, Any]
    options: list[dict[str, Any]]
    action_id: str


class SectionStaticSelectAccessory(TypedDict):
    type: str
    text: PlainText | MrkdwnText
    accessory: StaticSelectAccessory


class MultiStaticSelectAccessory(TypedDict):
    type: str
    placeholder: dict[str, Any]
    options: list[dict[str, Any]]
    action_id: str


class SectionMultiStaticSelectAccessory(TypedDict):
    type: str
    text: PlainText | MrkdwnText
    accessory: MultiStaticSelectAccessory


class MultiConversationsSelectAccessory(TypedDict):
    type: str
    placeholder: dict[str, Any]
    action_id: str


class SectionMultiConversationsSelectAccessory(TypedDict):
    type: str
    text: PlainText | MrkdwnText
    accessory: MultiConversationsSelectAccessory


class ButtonAccessory(TypedDict):
    type: str
    text: dict[str, Any]
    value: str
    action_id: str


class SectionButtonAccessory(TypedDict):
    type: str
    text: PlainText | MrkdwnText
    accessory: ButtonAccessory


class LinkButtonAccessory(TypedDict):
    type: str
    text: dict[str, Any]
    value: str
    url: str
    action_id: str


class SectionLinkButtonAccessory(TypedDict):
    type: str
    text: PlainText | MrkdwnText
    accessory: LinkButtonAccessory


class CheckboxAccessory(TypedDict):
    type: str
    options: list[dict[str, Any]]
    action_id: str


class SectionCheckboxAccessory(TypedDict):
    type: str
    text: PlainText | MrkdwnText
    accessory: CheckboxAccessory


class RadioButtonsAccessory(TypedDict):
    type: str
    options: list[dict[str, Any]]
    action_id: str


class SectionRadioButtonsAccessory(TypedDict):
    type: str
    text: PlainText | MrkdwnText
    accessory: RadioButtonsAccessory


class DatePickerAccessory(TypedDict):
    type: str
    initial_date: str
    placeholder: dict[str, Any]
    action_id: str


class SectionDatePickerAccessory(TypedDict):
    type: str
    text: PlainText | MrkdwnText
    accessory: DatePickerAccessory


class TimePickerAccessory(TypedDict):
    type: str
    initial_time: str
    placeholder: dict[str, Any]
    action_id: str


class SectionTimePickerAccessory(TypedDict):
    type: str
    text: PlainText | MrkdwnText
    accessory: TimePickerAccessory
