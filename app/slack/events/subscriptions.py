from datetime import datetime
from app.constants import BOT_IDS
from app.models import User
from app.slack.services.base import SlackService
from app.slack.types import (
    ActionBodyType,
    OverflowActionBodyType,
)

from slack_sdk.models.blocks import (
    Block,
    Option,
    OverflowMenuElement,
    SectionBlock,
    DividerBlock,
    UserSelectElement,
    ActionsBlock,
    ContextBlock,
    MarkdownTextObject,
)
from slack_sdk.models.views import View
from slack_bolt.async_app import AsyncAck, AsyncSay
from slack_sdk.web.async_client import AsyncWebClient

from app.utils import json_str_to_dict


async def open_subscribe_member_view(
    ack: AsyncAck,
    body: ActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
) -> None:
    """멤버 구독 모달을 엽니다."""
    await ack()

    target_user_value = body["actions"][0].get("value")
    if not target_user_value:
        target_user_id = None
        message = ""
    else:
        target_user_id = json_str_to_dict(target_user_value)["target_user_id"]
        message = _process_user_subscription(user, service, target_user_id)

    view = _get_subscribe_member_view(
        user_id=user.user_id,
        service=service,
        message=message,
        initial_target_user_id=target_user_id,
    )

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=view,
    )


async def subscribe_member(
    ack: AsyncAck,
    body: ActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
) -> None:
    """멤버를 구독합니다."""
    await ack()
    target_user_id = body["actions"][0].get("selected_user")
    if not target_user_id:
        return

    message = _process_user_subscription(user, service, target_user_id)
    view = _get_subscribe_member_view(
        user_id=user.user_id, service=service, message=message
    )

    await client.views_update(
        view_id=body["view"]["id"],
        view=view,
    )


def _process_user_subscription(
    user: User,
    service: SlackService,
    target_user_id: str,
) -> str:
    """
    멤버 구독을 처리합니다.
    만약, 구독이 성공하면 빈 문자열을 반환하고, 실패하면 에러 메시지를 반환합니다.
    """
    message = ""
    if target_user_id == user.user_id:
        message = "⚠️ 자기 자신은 구독할 수 없어요."

    if target_user_id in BOT_IDS:
        message = "⚠️ 봇은 구독할 수 없어요."

    if len(service.fetch_subscriptions_by_user_id(user_id=user.user_id)) >= 5:
        message = "⚠️ 구독은 최대 5명까지 가능해요."

    target_user = service.get_only_user(target_user_id)
    if not target_user:
        message = "⚠️ 구독할 멤버를 찾을 수 없습니다."

    if any(
        subscription.target_user_id == target_user_id
        for subscription in service.fetch_subscriptions_by_user_id(user_id=user.user_id)
    ):
        message = "⚠️ 이미 구독한 멤버입니다."

    if not message:
        service.create_subscription(
            user_id=user.user_id,
            target_user_id=target_user_id,
            target_user_channel=target_user.writing_channel_id,
        )

    return message


async def unsubscribe_member(
    ack: AsyncAck,
    body: OverflowActionBodyType,
    client: AsyncWebClient,
    say: AsyncSay,
    user: User,
    service: SlackService,
) -> None:
    """멤버 구독을 취소합니다."""
    await ack()

    subscription_id = body["actions"][0]["selected_option"]["value"]
    service.cancel_subscription(subscription_id)

    view = _get_subscribe_member_view(user_id=user.user_id, service=service)

    await client.views_update(
        view_id=body["view"]["id"],
        view=view,
    )


async def open_subscription_permalink(
    ack: AsyncAck,
    body: ActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
) -> None:
    """구독한 멤버의 새 글을 엽니다. 로깅을 위한 이벤트입니다."""
    await ack()


def _get_subscribe_member_view(
    *,
    user_id: str,
    service: SlackService,
    initial_target_user_id: str | None = None,
    message: str = "",
) -> View:
    """구독 목록과, 멤버를 구독할 수 있는 뷰를 반환합니다."""
    user_subscriptions = service.fetch_subscriptions_by_user_id(user_id=user_id)
    subscription_list_blocks = [
        SectionBlock(
            text=f"<@{subscription.target_user_id}> 님을 {datetime.strptime(subscription.created_at[:10], '%Y-%m-%d').strftime('%Y년 %m월 %d일')} 부터 구독하고 있어요.",
            accessory=OverflowMenuElement(
                action_id="unsubscribe_member",
                options=[
                    Option(text="구독 취소", value=subscription.id),
                ],
            ),
        )
        for subscription in user_subscriptions
    ]
    if subscription_list_blocks:
        subscription_list_blocks = [
            SectionBlock(text="*구독 목록*"),
            *subscription_list_blocks,
        ]

    subscribe_blocks: list[Block] = []
    subscribe_blocks.append(SectionBlock(text="*구독 하기*"))
    subscribe_blocks.append(
        ActionsBlock(
            elements=[
                UserSelectElement(
                    action_id="subscribe_member",
                    placeholder="구독할 멤버를 선택해주세요.",
                    initial_user=initial_target_user_id,
                ),
            ],
            block_id="select_target_user",
        )
    )
    if message:
        subscribe_blocks.append(
            ContextBlock(elements=[MarkdownTextObject(text=f"*{message}*")])
        )
    subscribe_blocks.append(
        ContextBlock(
            elements=[
                MarkdownTextObject(
                    text="구독한 멤버가 글을 제출하면 다음 날 오전 8시(한국 시간)에 DM으로 알림을 받을 수 있어요. 구독은 최대 5명까지 구독할 수 있으며, 취소는 구독 목록 우측의 `...` 또는 `더보기` 버튼을 통해 할 수 있어요."
                ),
            ],
        )
    )
    view = View(
        type="modal",
        title="멤버 구독",
        close="닫기",
        blocks=[
            SectionBlock(
                text=f"<@{user_id}> 님은 현재 {len(user_subscriptions)}명을 구독하고 있어요."
            ),
            DividerBlock(),
            *subscribe_blocks,
            DividerBlock(),
            *subscription_list_blocks,
        ],
    )

    return view
