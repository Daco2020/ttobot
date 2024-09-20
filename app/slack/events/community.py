import asyncio
import requests
from slack_sdk.web.async_client import AsyncWebClient
from app.exception import BotException
from app.models import User
from app.slack.services.base import SlackService
from app.slack.services.point import PointService
from app.slack.types import (
    ActionBodyType,
    MessageBodyType,
    ReactionBodyType,
    ViewBodyType,
)
from slack_bolt.async_app import AsyncAck, AsyncSay
from slack_sdk.models.views import View
from slack_sdk.models.blocks import (
    SectionBlock,
    InputBlock,
    UserMultiSelectElement,
    ActionsBlock,
    ButtonElement,
)
from app.config import settings
from app.utils import dict_to_json_str, json_str_to_dict

# TODO: 커피 챗 인증 횟수 확인 방법 강구. 앱 홈 화면에 표시할 수 있도록?


async def handle_coffee_chat_message(
    ack: AsyncAck,
    body: MessageBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """커피챗 인증 메시지인지 확인하고, 인증 모달을 전송합니다."""
    await ack()

    # 인증글에 답글로 커피챗 인증을 하는 경우
    if body["event"].get("thread_ts"):
        try:
            service.check_coffee_chat_proof(
                thread_ts=str(body["event"]["thread_ts"]),
                user_id=body["event"]["user"],
            )
        except BotException:
            # 인증 글에 대한 답글이 아니거나 이미 인증한 경우, 인증 대상이 아닌 경우이다.
            return

        service.create_coffee_chat_proof(
            ts=str(body["event"]["ts"]),
            thread_ts=str(body["event"]["thread_ts"]),
            user_id=body["event"]["user"],
            text=body["event"]["text"],
            files=body["event"].get("files", []),  # type: ignore
            selected_user_ids="",
        )

        await client.reactions_add(
            channel=body["event"]["channel"],
            timestamp=body["event"]["ts"],
            name="white_check_mark",
        )

        # 포인트 지급
        point_service.grant_if_coffee_chat_verified(
            user_id=body["event"]["user"], client=client
        )

        return

    # 2초 대기하는 이유는 메시지 보다 더 먼저 전송 될 수 있기 때문임
    await asyncio.sleep(2)
    text = "☕ 커피챗 인증을 시작하려면 아래 [ 커피챗 인증 ] 버튼을 눌러주세요."
    await client.chat_postEphemeral(
        user=user.user_id,
        channel=body["event"]["channel"],
        text=text,
        blocks=[
            SectionBlock(text=text),
            ActionsBlock(
                elements=[
                    ButtonElement(
                        text="안내 닫기",
                        action_id="cancel_coffee_chat_proof_button",
                    ),
                    ButtonElement(
                        text="커피챗 인증",
                        action_id="submit_coffee_chat_proof_button",
                        value=body["event"]["ts"],
                        style="primary",
                    ),
                ]
            ),
        ],
    )


async def cancel_coffee_chat_proof_button(
    ack: AsyncAck,
    body: ActionBodyType,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """커피챗 인증 안내를 닫습니다."""
    await ack()

    requests.post(
        body["response_url"],
        json={
            "response_type": "ephemeral",
            "delete_original": True,
        },
        timeout=5.0,
    )


async def submit_coffee_chat_proof_button(
    ack: AsyncAck,
    body: ActionBodyType,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """커피챗 인증을 제출합니다."""
    await ack()

    private_metadata = dict_to_json_str(
        {
            "ephemeral_url": body["response_url"],
            "message_ts": body["actions"][0]["value"],
        }
    )

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            title="커피챗 인증",
            submit="커피챗 인증하기",
            callback_id="submit_coffee_chat_proof_view",
            private_metadata=private_metadata,
            blocks=[
                SectionBlock(text="커피챗에 참여한 멤버들을 모두 선택해주세요.😊"),
                InputBlock(
                    block_id="participant",
                    label="커피챗 참여 멤버",
                    optional=False,
                    element=UserMultiSelectElement(
                        action_id="select",
                        placeholder="참여한 멤버들을 모두 선택해주세요.",
                        initial_users=[user.user_id],
                    ),
                ),
            ],
        ),
    )


async def submit_coffee_chat_proof_view(
    ack: AsyncAck,
    body: ViewBodyType,
    client: AsyncWebClient,
    say: AsyncSay,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """커피챗 인증을 처리합니다."""
    await ack()

    private_metadata = json_str_to_dict(body["view"]["private_metadata"])
    ephemeral_url = private_metadata["ephemeral_url"]
    message_ts = private_metadata["message_ts"]

    history = await client.conversations_history(
        channel=settings.COFFEE_CHAT_PROOF_CHANNEL,
        latest=message_ts,
        limit=1,
        inclusive=True,
    )
    message = history["messages"][0]
    selected_users = body["view"]["state"]["values"]["participant"]["select"][
        "selected_users"
    ]

    service.create_coffee_chat_proof(
        ts=message_ts,
        thread_ts="",
        user_id=user.user_id,
        text=message["text"],
        files=message.get("files", []),
        selected_user_ids=",".join(
            selected_user
            for selected_user in selected_users
            if selected_user != user.user_id
        ),
    )

    await client.reactions_add(
        channel=settings.COFFEE_CHAT_PROOF_CHANNEL,
        timestamp=message_ts,
        name="white_check_mark",
    )

    # 포인트 지급
    point_service.grant_if_coffee_chat_verified(user_id=user.user_id, client=client)

    user_call_text = ",".join(
        f"<@{selected_user}>"
        for selected_user in selected_users
        if selected_user != user.user_id  # 본인 제외
    )

    if user_call_text:
        await client.chat_postMessage(
            channel=settings.COFFEE_CHAT_PROOF_CHANNEL,
            thread_ts=message_ts,
            text=f"{user_call_text} \n\n😊 커피챗 인증을 위해 꼭 후기를 남겨주세요. 인증이 확인된 멤버는 ✅가 표시돼요.",
        )

    # 나에게만 표시 메시지 수정하는 요청(slack bolt 에서는 지원하지 않음)
    requests.post(
        ephemeral_url,
        json={
            "response_type": "ephemeral",
            "delete_original": True,
        },
        timeout=5.0,
    )


async def handle_reaction_added(
    ack: AsyncAck,
    body: ReactionBodyType,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """리액션 추가 이벤트를 처리합니다."""
    await ack()

    service.create_reaction(
        type=body["event"]["type"],
        user_id=body["event"]["user"],
        reaction=body["event"]["reaction"],
        reaction_ts=body["event"]["event_ts"],
        item_type=body["event"]["item"]["type"],
        item_user_id=body["event"].get("item_user", "알 수 없음"),
        item_channel=body["event"]["item"]["channel"],
        item_ts=body["event"]["item"]["ts"],
    )


async def handle_reaction_removed(
    ack: AsyncAck,
    body: ReactionBodyType,
    user: User,
    service: SlackService,
    point_service: PointService,
):
    """리액션 삭제 이벤트를 처리합니다."""
    await ack()
