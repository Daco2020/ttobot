from typing import TypedDict


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


class Authorization(TypedDict):
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
    authorizations: list[Authorization]
    is_ext_shared_channel: bool
    event_context: str


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


class TeamType(TypedDict):
    id: str
    domain: str


class UserType(TypedDict):
    id: str
    username: str
    name: str
    team_id: str


class ViewType(TypedDict):
    id: str
    team_id: str
    type: str
    blocks: list[dict]
    private_metadata: str
    callback_id: str
    state: dict[str, dict]
    hash: str
    title: dict[str, str]
    clear_on_close: bool
    notify_on_close: bool
    close: str
    submit: dict[str, str]
    previous_view_id: str
    root_view_id: str
    app_id: str
    external_id: str
    app_installed_team_id: str
    bot_id: str


class ViewBodyType(TypedDict):
    type: str
    team: TeamType
    user: UserType
    api_app_id: str
    token: str
    trigger_id: str
    view: ViewType
    response_urls: list[str]
    is_enterprise_install: bool
    enterprise: str


class ContainerType(TypedDict):
    type: str
    message_ts: str
    channel_id: str
    is_ephemeral: bool


class ChannelType(TypedDict):
    id: str
    name: str


class MessageType(TypedDict):
    user: str
    type: str
    ts: str
    bot_id: str
    app_id: str
    text: str
    team: str
    blocks: list[dict]


class ActionType(TypedDict):
    action_id: str
    block_id: str
    text: dict[str, str]
    value: str
    type: str
    action_ts: str


class ActionBodyType(TypedDict):
    type: str
    user: UserType
    api_app_id: str
    token: str
    container: ContainerType
    trigger_id: str
    team: TeamType
    enterprise: str
    is_enterprise_install: bool
    channel: ChannelType
    message: MessageType
    state: dict[str, dict]
    response_url: str
    view: ViewType
    actions: list[ActionType]


class OverflowActionType(TypedDict):
    type: str
    action_id: str
    block_id: str
    selected_option: dict[str, str]
    action_ts: str


class OverflowActionBodyType(TypedDict):
    type: str
    user: UserType
    api_app_id: str
    token: str
    container: ContainerType
    trigger_id: str
    team: TeamType
    enterprise: str
    is_enterprise_install: bool
    view: ViewType
    actions: list[OverflowActionType]


class BlockActionBodyType(TypedDict):
    type: str
    user: UserType
    api_app_id: str
    token: str
    container: ContainerType
    trigger_id: str
    team: TeamType
    enterprise: str
    is_enterprise_install: bool
    channel: ChannelType
    message: MessageType
    state: dict[str, dict]
    response_url: str
    actions: list[ActionType]


class MessageEvent(TypedDict):
    user: str
    type: str
    ts: str
    client_msg_id: str
    text: str
    team: str
    blocks: list[dict]
    channel: str
    event_ts: str
    channel_type: str
    thread_ts: str | None  # 상위 메시지의 timestamp


class MessageBodyType(TypedDict):
    token: str
    team_id: str
    context_team_id: str
    context_enterprise_id: str | None
    api_app_id: str
    event: MessageEvent
    type: str
    event_id: str
    event_time: int
    authorizations: list[Authorization]
    is_ext_shared_channel: bool
    event_context: str
