from app.constants import BOT_IDS
from app.models import User
from app.slack.services.base import SlackService
from app.slack.types import (
    ActionBodyType,
    OverflowActionBodyType,
    ViewBodyType,
)

from slack_sdk.models.blocks import (
    Option,
    OverflowMenuElement,
    SectionBlock,
    DividerBlock,
    UserSelectElement,
    InputBlock,
    ContextBlock,
    MarkdownTextObject,
)
from slack_sdk.models.views import View
from slack_bolt.async_app import AsyncAck, AsyncSay
from slack_sdk.web.async_client import AsyncWebClient


async def subscribe_member_by_action(
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


async def subscribe_member_by_view(
    ack: AsyncAck,
    body: ViewBodyType,
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


def _get_subscribe_member_view(
    *,
    user_id: str,
    service: SlackService,
    initial_target_user_id: str | None = None,
) -> View:
    """구독 목록과, 멤버를 구독할 수 있는 뷰를 반환합니다."""
    user_subscriptions = service.fetch_subscriptions_by_user_id(user_id=user_id)

    subscription_list_blocks = [
        SectionBlock(
            text=f"<@{subscription.target_user_id}> 님을 {subscription.created_at} 부터 구독하고 있어요.",
            accessory=OverflowMenuElement(
                action_id="unsubscribe_target_user",
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

    view = View(
        type="modal",
        title="멤버 구독",
        callback_id="handle_subscribe_member_view",
        submit="구독하기",
        close="닫기",
        blocks=[
            SectionBlock(
                text=f"<@{user_id}> 님은 현재 {len(user_subscriptions)}명을 구독하고 있어요."
            ),
            DividerBlock(),
            InputBlock(
                block_id="select_target_user",
                label="멤버 구독하기",
                element=UserSelectElement(
                    action_id="select",
                    placeholder="구독할 멤버를 선택해주세요.",
                    initial_user=initial_target_user_id,
                ),
            ),
            ContextBlock(
                elements=[
                    MarkdownTextObject(
                        text="구독한 멤버가 글을 제출하면 알림을 받아 볼 수 있는 기능입니다.\n"
                        "알림은 글 제출 다음날 오전 8시(한국 시간)에 DM 으로 전달합니다.\n"
                        "구독 취소는 구독 목록 우측 `...` 버튼을 눌러 취소할 수 있습니다.\n"
                        "최대 5명까지 구독 할 수 있습니다.",
                    ),
                ],
            ),
            DividerBlock(),
            *subscription_list_blocks,
        ],
    )

    return view


async def handle_subscribe_member_view(
    ack: AsyncAck,
    body: ViewBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
) -> None:
    """멤버 구독을 핸들링합니다."""
    target_user_id = body["view"]["state"]["values"]["select_target_user"]["select"][
        "selected_user"
    ]

    if target_user_id == user.user_id:
        await ack(
            response_action="errors",
            errors={"select_target_user": "자기 자신은 구독할 수 없어요. 😅"},
        )
        return

    if target_user_id in BOT_IDS:
        await ack(
            response_action="errors",
            errors={"select_target_user": "봇은 구독할 수 없어요. 😉"},
        )
        return

    if len(service.fetch_subscriptions_by_user_id(user_id=user.user_id)) >= 5:
        await ack(
            response_action="errors",
            errors={"select_target_user": "구독은 최대 5명까지 가능해요. 😭"},
        )
        return

    target_user = service.get_only_user(target_user_id)
    if not target_user:
        await ack(
            response_action="errors",
            errors={"select_target_user": "구독할 멤버를 찾을 수 없습니다. 😅"},
        )
        return

    # TODO: 이미 구독했다면 할 수 없습니다.
    await ack()

    service.create_subscription(
        user_id=user.user_id,
        target_user_id=target_user_id,
        target_user_channel=target_user.channel_id,
    )

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            title="멤버 구독 완료",
            callback_id="subscribe_member_by_view",
            blocks=[
                SectionBlock(
                    text=f"<@{target_user_id}> 님의 글 구독을 시작합니다! 🤩",
                ),
            ],
            submit="돌아가기",
            close="닫기",
        ),
    )


async def unsubscribe_target_user(
    ack: AsyncAck,
    body: OverflowActionBodyType,
    client: AsyncWebClient,
    say: AsyncSay,
    user: User,
    service: SlackService,
) -> None:
    """구독을 취소합니다."""
    subscription_id = body["actions"][0]["selected_option"]["value"]
    subscription = service.get_subscription(subscription_id)
    if not subscription:
        await ack(
            response_action="errors",
            errors={"unsubscribe_target_user": "구독을 찾을 수 없습니다."},
        )
        return

    await ack()

    target_user_id = subscription.target_user_id
    service.cancel_subscription(subscription.id)

    await client.views_update(
        view_id=body["view"]["id"],
        view=View(
            type="modal",
            title="구독 취소 완료",
            callback_id="subscribe_member_by_view",
            blocks=[
                SectionBlock(
                    text=f"<@{target_user_id}> 님의 글 구독을 취소했어요. 🫡",
                ),
            ],
            submit="돌아가기",
            close="닫기",
        ),
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
