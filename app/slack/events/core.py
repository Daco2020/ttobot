import tenacity

from app.client import SpreadSheetClient
from app.config import settings
from app.constants import HELP_TEXT
from app.models import User
from app.slack.services.base import SlackService
from app.slack.services.point import PointService
from app.slack.types import (
    ActionBodyType,
    AppMentionBodyType,
    CommandBodyType,
    HomeTabEventType,
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
    TextObject,
    HeaderBlock,
    ContextBlock,
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


async def open_deposit_view(
    ack: AsyncAck,
    body: CommandBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
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


async def open_submission_history_view(
    ack: AsyncAck,
    body: CommandBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
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


async def open_help_view(
    ack: AsyncAck,
    body: CommandBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """도움말을 조회합니다."""
    await ack()

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            title="도움말",
            close="닫기",
            blocks=[SectionBlock(text=HELP_TEXT)],
        ),
    )


async def admin_command(
    ack: AsyncAck,
    body: CommandBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
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
    point_service: PointService,
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
    point_service: PointService,
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
    point_service: PointService,
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
        text=f"<@{user_id}> 님의 채널 초대를 시작합니다.\n\n채널 수 : {len(channel_ids)} 개\n",
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


async def handle_home_tab(
    event: HomeTabEventType,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
):
    """홈 탭을 열었을 때의 이벤트를 처리합니다."""

    # TODO: 현재는 임시로 컨셉만 구현한 상태입니다.
    await client.views_publish(
        user_id=user.user_id,
        view=View(
            type="home",
            blocks=[
                SectionBlock(
                    text=TextObject(
                        type="mrkdwn",
                        text=f"<@{user.user_id}> 님 안녕하세요! 저는 또봇이에요~ 👋",
                    ),
                ),
                HeaderBlock(
                    text="😊 무엇을 도와드릴까요?",
                ),
                ContextBlock(
                    elements=[
                        TextObject(
                            type="mrkdwn",
                            text="아래 버튼을 눌러서 원하는 기능을 이용해보세요.",
                        )
                    ],
                ),
                ActionsBlock(
                    elements=[
                        ButtonElement(
                            text="현재 남아있는 예치금을 알고 싶어요",
                            action_id="open_deposit_view",
                            value="open_deposit_view",
                        ),
                        ButtonElement(
                            text="지금까지 제출한 글을 확인하고 싶어요",
                            action_id="open_submission_history_view",
                            value="open_submission_history_view",
                        ),
                        ButtonElement(
                            text="또봇에 어떤 기능들이 있는지 궁금해요",
                            action_id="open_help_view",
                            value="open_help_view",
                        ),
                    ],
                ),
                DividerBlock(),
                HeaderBlock(
                    text=f"✏️ {user.name}님의 `자루` 현황이에요!",
                ),
                ContextBlock(
                    elements=[
                        TextObject(
                            type="mrkdwn",
                            text="`자루`는 글또 내에서 서로 주고 받을 수 있는 `커뮤니티 점수`를 의미해요.\n자루는 멤버에게 직접 받을 수도 있고, 슬랙 커뮤니티 활동을 통해 얻을 수도 있어요. :moneybag:\n자루를 보내려면 어디서든 `/자루보내기` 명령어를 입력해보세요. 단, 자루는 하루에 하나만 보낼 수 있답니다. 🤭",
                        )
                    ],
                ),
                SectionBlock(
                    text="지금까지 받은 자루 : *13.7 X* ✏️\n지금까지 보낸 자루 : *5 X* ✏️",
                ),
                ActionsBlock(
                    elements=[
                        ButtonElement(
                            text="지금 바로 자루 보내기",
                            action_id="3",
                            value="3",
                            style="primary",
                        ),
                        ButtonElement(
                            text="지금까지 받은 자루 확인하기",
                            action_id="1",
                            value="1",
                        ),
                        ButtonElement(
                            text="지금까지 보낸 자루 확인하기",
                            action_id="2",
                            value="2",
                        ),
                        ButtonElement(
                            text="내 자루 랭킹 확인하기",
                            action_id="4",
                            value="4",
                        ),
                    ],
                ),
                DividerBlock(),
                HeaderBlock(
                    text="📬 글또에서 발행한 콘텐츠를 확인해보세요.",
                ),
                ContextBlock(
                    elements=[
                        TextObject(
                            type="mrkdwn",
                            text="유용한 글쓰기 팁과 커뮤니티에서 벌어지는 다양한 이야기를 확인해보세요.",
                        )
                    ],
                ),
                SectionBlock(
                    text="블라블라~\n블라블라~\n블라블라~\n",
                ),
                DividerBlock(),
                HeaderBlock(
                    text="📚 이런 소모임은 어떠세요?",
                ),
                ContextBlock(
                    elements=[
                        TextObject(
                            type="mrkdwn",
                            text="최근에 새롭게 열렸거나 활동이 많은 소모임을 추천해드려요.",
                        )
                    ],
                ),
                SectionBlock(
                    text="블라블라~\n블라블라~\n블라블라~\n",
                ),
                DividerBlock(),
                HeaderBlock(
                    text="📅 글또 일정을 확인해보세요.",
                ),
                ContextBlock(
                    elements=[
                        TextObject(
                            type="mrkdwn",
                            text="글또의 다양한 일정들을 확인하고 참여해보세요.",
                        )
                    ],
                ),
                SectionBlock(
                    text="블라블라~\n블라블라~\n블라블라~\n",
                ),
            ],
        ),
    )
