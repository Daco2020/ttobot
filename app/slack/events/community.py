import orjson
import requests
from slack_sdk.web.async_client import AsyncWebClient
from app.models import User
from app.models import CoffeeChatProof
from app.slack.services import SlackService
from app.slack.types import (
    ActionBodyType,
    MessageBodyType,
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


async def handle_coffee_chat_message(
    ack: AsyncAck,
    body: MessageBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
) -> None:
    """커피챗 인증 메시지인지 확인하고, 인증 모달을 전송합니다."""
    await ack()

    if body["event"]["channel"] != "C05J87UPC3F":
        return

    thread_ts = body["event"].get("thread_ts")
    if thread_ts:
        # TODO: thread_ts 로 커피챗 인증글이 있다면 인증을 할 수 있는 스레드이다.
        # TODO: 커피챗.user_id==user.user_id and 커피챗.ts==thread_ts 커피챗 인증글이 있다면 이미 해당 유저는 인증이 완료된 상태이다.

        image_urls = ",".join(
            file["thumb_1024"] for file in body["event"].get("files", [])  # type: ignore
        )
        CoffeeChatProof(
            ts=body["event"]["ts"],
            thread_ts=thread_ts,
            user_id=body["event"]["user"],
            text=body["event"]["text"],
            image_urls=image_urls,
        )

        # TODO: 데이터 저장

        await client.reactions_add(
            channel=body["event"]["channel"],
            timestamp=body["event"]["ts"],
            name="white_check_mark",
        )
        return

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
                        style="danger",
                    )
                ]
            ),
            ActionsBlock(
                elements=[
                    ButtonElement(
                        text="커피챗 인증",
                        action_id="submit_coffee_chat_proof_button",
                        value=body["event"]["ts"],
                        style="primary",
                    )
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
) -> None:
    """커피챗 인증을 제출합니다."""
    await ack()

    private_metadata = orjson.dumps(
        {
            "ephemeral_url": body["response_url"],
            "message_ts": body["actions"][0]["value"],
        }
    ).decode("utf-8")

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
) -> None:
    """커피챗 인증을 처리합니다."""
    await ack()

    private_metadata = orjson.loads(body["view"]["private_metadata"])
    ephemeral_url = private_metadata["ephemeral_url"]
    message_ts = private_metadata["message_ts"]

    history = await client.conversations_history(
        channel="C05J87UPC3F",
        latest=message_ts,
        limit=1,
        inclusive=True,
    )
    message = history["messages"][0]
    selected_users = body["view"]["state"]["values"]["participant"]["select"][
        "selected_users"
    ]

    text = message["text"]
    image_urls = ",".join(file["thumb_1024"] for file in message.get("files", []))

    participant_user_ids = ",".join(
        f"<@{selected_user}>"
        for selected_user in selected_users
        if selected_user != user.user_id  # 본인 제외
    )

    CoffeeChatProof(
        ts=message_ts,
        user_id=user.user_id,
        text=text,
        image_urls=image_urls,
    )

    # TODO: 데이터 저장

    if participant_user_ids:
        await client.chat_postMessage(
            channel="C05J87UPC3F",
            thread_ts=message_ts,
            text=f"{participant_user_ids} 커피챗 인증을 위해 후기를 남겨주세요. ☕😊",
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
