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

    view = _get_subscribe_member_view(user_id=user.user_id, service=service)

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

    error_message = ""
    if target_user_id == user.user_id:
        error_message = "⚠️ 자기 자신은 구독할 수 없어요."

    if target_user_id in BOT_IDS:
        error_message = "⚠️ 봇은 구독할 수 없어요."

    if len(service.fetch_subscriptions_by_user_id(user_id=user.user_id)) >= 5:
        error_message = "⚠️ 구독은 최대 5명까지 가능해요."

    target_user = service.get_only_user(target_user_id)
    if not target_user:
        error_message = "⚠️ 구독할 멤버를 찾을 수 없습니다."

    if any(
        subscription.target_user_id == target_user_id
        for subscription in service.fetch_subscriptions_by_user_id(user_id=user.user_id)
    ):
        error_message = "⚠️ 이미 구독한 멤버입니다."

    if not error_message:
        service.create_subscription(
            user_id=user.user_id,
            target_user_id=target_user_id,
            target_user_channel=target_user.channel_id,
        )

    view = _get_subscribe_member_view(
        user_id=user.user_id, service=service, error_message=error_message
    )

    await client.views_update(
        view_id=body["view"]["id"],
        view=view,
    )


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
    """구독 링크를 엽니다. 로깅을 위한 이벤트입니다."""
    await ack()


def _get_subscribe_member_view(
    *,
    user_id: str,
    service: SlackService,
    initial_target_user_id: str | None = None,
    error_message: str | None = None,
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
                    placeholder=error_message or "구독할 멤버를 선택해주세요.",
                    initial_user=initial_target_user_id,
                ),
            ],
            block_id="select_target_user",
        )
    )
    if error_message:
        subscribe_blocks.append(
            ContextBlock(elements=[MarkdownTextObject(text=f"*{error_message}*")])
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
