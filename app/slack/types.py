from typing import TypedDict


class CommandBodyType(TypedDict):
    token: str
    team_id: str
    team_domain: str
    channel_id: str
    channel_name: str
    user_id: str
    user_name: str
    command: str
    text: str
    api_app_id: str
    is_enterprise_install: str
    response_url: str
    trigger_id: str


class AppMentionEvent(TypedDict):
    user: str
    type: str
    ts: str
    client_msg_id: str
    text: str
    team: str
    blocks: list[dict]
    channel: str
    event_ts: str


class AppMentionAuthorization(TypedDict):
    enterprise_id: str
    team_id: str
    user_id: str
    is_bot: bool
    is_enterprise_install: bool


class AppMentionBodyType(TypedDict):
    token: str
    team_id: str
    api_app_id: str
    event: AppMentionEvent
    type: str
    event_id: str
    event_time: int
    authorizations: list[AppMentionAuthorization]
    is_ext_shared_channel: bool
    event_context: str
