import tenacity

from app.client import SpreadSheetClient
from app.config import settings
from app.constants import HELP_TEXT
from app.models import User
from app.slack.services import SlackService
from app.slack.types import (
    ActionBodyType,
    AppMentionBodyType,
    CommandBodyType,
    ViewBodyType,
    ViewType,
)
from app.store import Store

from slack_sdk.models.blocks import (
    SectionBlock,
    DividerBlock,
    ActionsBlock,
    ButtonElement,
    ChannelMultiSelectElement,
    UserSelectElement,
    InputBlock,
)
from slack_sdk.models.views import View
from slack_bolt.async_app import AsyncAck, AsyncSay
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError


async def handle_app_mention(
    ack: AsyncAck,
    body: AppMentionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
) -> None:
    """앱 멘션 호출 시 도움말 메시지를 전송합니다."""
    await ack()


async def deposit_command(
    ack: AsyncAck,
    body: CommandBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
) -> None:
    """예치금을 조회합니다."""
    await ack()

    if not user.deposit:
        text = "현재 예치금 확인 중이에요."
    else:
        deposit_link = (
            f"\n\n*<{settings.DEPOSIT_SHEETS_URL}|{'예치금 현황 자세히 확인하기'}>*"
            if settings.DEPOSIT_SHEETS_URL
            else ""
        )
        text = (
            f"현재 남은 예치금은 {format(int(user.deposit), ',d')} 원 이에요."
            + deposit_link
        )

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            title=f"{user.name}님의 예치금 현황",
            close="닫기",
            blocks=[SectionBlock(text=text)],
        ),
    )


async def history_command(
    ack: AsyncAck,
    body: CommandBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
) -> None:
    """제출 내역을 조회합니다."""
    await ack()

    round, due_date = user.get_due_date()
    guide_message = f"\n*현재 회차는 {round}회차, 마감일은 {due_date} 이에요."

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            title=f"{user.name}님의 제출 내역",
            close="닫기",
            blocks=[
                SectionBlock(text=user.submit_history),
                DividerBlock(),
                SectionBlock(text=guide_message),
            ],
        ),
    )


async def help_command(
    ack: AsyncAck,
    body: CommandBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
) -> None:
    """도움말을 조회합니다."""
    await ack()

    # 또봇이 추가된 채널만 전송할 수 있기 때문에 개인 디엠으로 보내도록 통일.
    await client.chat_postEphemeral(
        channel=user.user_id,
        user=user.user_id,
        text=HELP_TEXT,
    )


async def admin_command(
    ack: AsyncAck,
    body: CommandBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
) -> None:
    """관리자 메뉴를 조회합니다."""
    await ack()

    if user.user_id not in settings.ADMIN_IDS:
        raise PermissionError("`/관리자` 명령어는 관리자만 호출할 수 있어요. 🤭")

    text = "관리자 메뉴입니다."
    await client.chat_postEphemeral(
        channel=body["channel_id"],
        user=user.user_id,
        text=text,
        blocks=[
            SectionBlock(text=text),
            ActionsBlock(
                elements=[
                    ButtonElement(
                        text="데이터 동기화",
                        action_id="sync_store",
                        value="sync_store",
                    ),
                    ButtonElement(
                        text="채널 초대",
                        action_id="invite_channel",
                        value="invite_channel",
                    ),
                ],
            ),
        ],
    )


async def handle_sync_store(
    ack: AsyncAck,
    body: ActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
) -> None:
    """데이터 동기화를 수행합니다."""
    await ack()

    try:
        await client.chat_postMessage(
            channel=settings.ADMIN_CHANNEL, text="데이터 동기화 시작"
        )
        sheet_client = SpreadSheetClient()
        store = Store(client=sheet_client)
        store.bulk_upload("logs")
        store.backup("contents")
        store.initialize_logs()
        store.pull()

        await client.chat_postMessage(
            channel=settings.ADMIN_CHANNEL, text="데이터 동기화 완료"
        )

    except Exception as e:
        await client.chat_postMessage(channel=settings.ADMIN_CHANNEL, text=str(e))


async def handle_invite_channel(
    ack: AsyncAck,
    body: ActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
) -> None:
    """채널 초대를 수행합니다."""
    await ack()

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            title="채널 초대",
            submit="채널 초대하기",
            callback_id="invite_channel_view",
            close="닫기",
            blocks=[
                SectionBlock(
                    text="초대하고 싶은 멤버와 채널을 선택해주세요.",
                ),
                InputBlock(
                    block_id="user",
                    label="멤버",
                    optional=False,
                    element=UserSelectElement(
                        action_id="select_user",
                        placeholder="멤버를 선택해주세요.",
                    ),
                ),
                InputBlock(
                    block_id="channel",
                    label="채널",
                    optional=True,
                    element=ChannelMultiSelectElement(
                        action_id="select_channels",
                        placeholder="채널을 선택하지 않으면 모든 공개 채널에 초대합니다.",
                    ),
                ),
            ],
        ),
    )


async def handle_invite_channel_view(
    ack: AsyncAck,
    body: ViewBodyType,
    client: AsyncWebClient,
    view: ViewType,
    say: AsyncSay,
    user: User,
    service: SlackService,
) -> None:
    """채널 초대를 수행합니다."""
    await ack()

    values = body["view"]["state"]["values"]
    user_id = values["user"]["select_user"]["selected_user"]
    channel_ids = values["channel"]["select_channels"]["selected_channels"]

    if not channel_ids:
        channel_ids = await _fetch_public_channel_ids(client)

    await client.chat_postMessage(
        channel=settings.ADMIN_CHANNEL,
        text=f"<@{user_id}> 님의 채널 초대를 시작합니다.\n\n채널 수 : {len(channel_ids)} 개\n채널 아이디 : {channel_ids}\n",
    )

    for channel_id in channel_ids:
        await _invite_channel(client, user_id, channel_id)

    await client.chat_postMessage(
        channel=settings.ADMIN_CHANNEL,
        text="채널 초대가 완료되었습니다.",
    )


@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_fixed(1),
    reraise=True,
)
async def _fetch_public_channel_ids(client: AsyncWebClient) -> list[str]:
    """모든 공개 채널의 아이디를 조회합니다."""
    res = await client.conversations_list(limit=500, types="public_channel")
    return [channel["id"] for channel in res["channels"]]


@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_fixed(1),
    reraise=True,
)
async def _invite_channel(
    client: AsyncWebClient,
    user_id: str,
    channel_id: str,
) -> None:
    """채널에 멤버를 초대합니다."""
    try:
        await client.conversations_invite(channel=channel_id, users=user_id)
        result = " -> ✅ (채널 초대)"
    except SlackApiError as e:
        # 봇이 채널에 없는 경우, 채널에 참여하고 초대합니다.
        if e.response["error"] == "not_in_channel":
            await client.conversations_join(channel=channel_id)
            await client.conversations_invite(channel=channel_id, users=user_id)
            result = " -> ✅ (또봇도 함께 채널 초대)"
        elif e.response["error"] == "already_in_channel":
            result = " -> ✅ (이미 채널에 참여 중)"
        elif e.response["error"] == "cant_invite_self":
            result = " -> ✅ (또봇이 자기 자신을 초대)"
        else:
            link = "<https://api.slack.com/methods/conversations.invite#errors|문서 확인하기>"
            result = f" -> 😵 ({e.response['error']}) 👉 {link}"

    await client.chat_postMessage(
        channel=settings.ADMIN_CHANNEL,
        text=f"\n<#{channel_id}>" + result,
    )
