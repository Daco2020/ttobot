import csv
import os
import tenacity

from app.client import SpreadSheetClient
from app.config import settings
from app.models import CoffeeChatProof, Content, PointHistory, User
from app.slack.services.base import SlackService
from app.slack.services.point import PointMap, PointService
from app.slack.types import (
    ActionBodyType,
    AppMentionBodyType,
    ChannelCreatedBodyType,
    CommandBodyType,
    HomeTabEventType,
    ViewBodyType,
    ViewType,
)
from app.store import Store

from slack_sdk.models.blocks import (
    Block,
    SectionBlock,
    DividerBlock,
    ActionsBlock,
    ButtonElement,
    PlainTextInputElement,
    ChannelMultiSelectElement,
    UserSelectElement,
    InputBlock,
    TextObject,
    HeaderBlock,
    ContextBlock,
    MarkdownTextObject,
)
from slack_sdk.models.views import View
from slack_bolt.async_app import AsyncAck, AsyncSay
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from app.utils import ts_to_dt


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
    guide_message = f"\n현재 회차는 {round}회차, 마감일은 {due_date} 이에요."
    header_blocks = [SectionBlock(text={"type": "mrkdwn", "text": guide_message})]

    blocks: list[Block] = []
    max_items = 12
    for content in user.fetch_contents(descending=True)[:max_items]:
        blocks.append(DividerBlock())
        round = content.get_round()
        if content.type == "submit":
            submit_head = f"✅  *{round}회차 제출*  |  {content.dt}"
            blocks.append(
                SectionBlock(
                    text={
                        "type": "mrkdwn",
                        "text": f"{submit_head}\n링크 - *<{content.content_url}|{content.title}>*",
                    }
                )
            )
        else:  # 패스인 경우
            pass_head = f"▶️  *{round}회차 패스*  |  {content.dt}"
            blocks.append(
                SectionBlock(
                    text={
                        "type": "mrkdwn",
                        "text": pass_head,
                    }
                )
            )

    footer_blocks = []
    if blocks:
        footer_blocks = [
            DividerBlock(),
            SectionBlock(
                text="글 제출 내역은 최근 12개까지만 표시됩니다.\n전체 내역을 확인하려면 아래 버튼을 눌러주세요.",
            ),
            ActionsBlock(
                elements=[
                    ButtonElement(
                        text="전체 내역 다운로드",
                        action_id="download_submission_history",
                        value="download_submission_history",
                        style="primary",
                    ),
                ],
            ),
        ]
    else:
        blocks.append(
            SectionBlock(text={"type": "mrkdwn", "text": "글 제출 내역이 없어요."})
        )

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            title={"type": "plain_text", "text": f"{user.name}님의 글 제출 내역"},
            close={"type": "plain_text", "text": "닫기"},
            blocks=header_blocks + blocks + footer_blocks,
        ),
    )


async def download_submission_history(
    ack: AsyncAck,
    body: ActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """글 제출 내역을 CSV 파일로 다운로드합니다."""
    await ack()

    response = await client.conversations_open(users=user.user_id)
    dm_channel_id = response["channel"]["id"]

    contents = user.fetch_contents()
    if not contents:
        await client.chat_postMessage(
            channel=dm_channel_id, text="글 제출 내역이 없습니다.1"
        )
        return None

    # 사용자의 제출내역을 CSV 파일로 임시 저장 후 전송
    temp_dir = "temp/submission_histories"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    temp_file_path = f"{temp_dir}/{user.name}-글-제출-내역.csv"
    with open(temp_file_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(
            csvfile,
            Content.fieldnames(),
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows([each.model_dump() for each in contents])

    res = await client.files_upload_v2(
        channel=dm_channel_id,  #####
        file=temp_file_path,
        initial_comment=f"<@{user.user_id}> 님의 글 제출 내역 입니다.",
    )

    await client.chat_postMessage(
        channel=dm_channel_id,
        text=f"<@{user.user_id}> 님의 <{res['file']['permalink']}|글 제출 내역> 입니다.",
    )

    # 임시로 생성한 CSV 파일을 삭제
    os.remove(temp_file_path)


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
            title={"type": "plain_text", "text": "또봇 도움말"},
            close={"type": "plain_text", "text": "닫기"},
            blocks=[
                # 인사말 섹션
                SectionBlock(
                    text={
                        "type": "mrkdwn",
                        "text": "👋🏼 *반가워요!*\n저는 글또 활동을 도와주는 *또봇* 이에요. "
                        "여러분이 글로 더 많이 소통할 수 있도록 다양한 기능을 제공하고 있어요.",
                    }
                ),
                DividerBlock(),
                # 명령어 안내
                SectionBlock(
                    text={
                        "type": "mrkdwn",
                        "text": "*💬 사용 가능한 명령어 안내*\n\n"
                        "*`/제출`* - 이번 회차의 글을 제출할 수 있어요.\n"
                        "*`/패스`* - 이번 회차의 글을 패스할 수 있어요.\n"
                        "*`/제출내역`* - 자신의 글 제출내역을 볼 수 있어요.\n"
                        "*`/검색`* - 다른 사람들의 글을 검색할 수 있어요.\n"
                        "*`/북마크`* - 북마크한 글을 볼 수 있어요.\n"
                        "*`/예치금`* - 현재 남은 예치금을 알려드려요.\n"
                        "*`/도움말`* - 또봇 사용법을 알려드려요.\n"
                        "*`/종이비행기`* - 종이비행기를 보낼 수 있어요.\n",
                    }
                ),
                DividerBlock(),
                # 문의 및 코드 안내
                SectionBlock(
                    text={
                        "type": "mrkdwn",
                        "text": "🙌 *도움이 필요하신가요?*\n\n"
                        f"궁금한 사항이 있다면 <#{settings.SUPPORT_CHANNEL}> 채널로 문의해주세요!\n"
                        "또봇 코드가 궁금하다면 👉🏼 *<https://github.com/Daco2020/ttobot|또봇 깃허브>* 로 놀러오세요~ 🤗",
                    }
                ),
            ],
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
    user: User | None,
    service: SlackService | None,
    point_service: PointService | None,
):
    """홈 탭을 열었을 때의 이벤트를 처리합니다."""
    if not user:
        await client.views_publish(
            user_id=event["user"],
            view=View(
                type="home",
                blocks=[
                    HeaderBlock(
                        text="👋 반가워요! 저는 또봇이에요.",
                    ),
                    DividerBlock(),
                    SectionBlock(
                        text="[홈] 탭은 글또 OT 이후에 공개될 예정이에요. 🙇‍♂️\n만약 OT 이후에도 해당 화면이 표시된다면 [0_글또봇질문] 채널로 문의해주세요.",
                    ),
                ],
            ),
        )
        return

    # 포인트 히스토리를 포함한 유저를 가져온다.
    user_point_history = point_service.get_user_point(user_id=user.user_id)
    combo_count = user.get_continuous_submit_count()
    next_combo_point = ""
    if combo_count == 0:
        pass
    elif combo_count in [3, 6, 9]:
        next_combo_point = "*+ ???(특별 콤보 보너스)* "
    else:
        next_combo_point = (
            "*+ " + str(PointMap.글_제출_콤보.point * combo_count) + "(콤보 보너스)* "
        )

    paper_planes = service.fetch_current_week_paper_planes(user_id=user.user_id)
    remain_paper_planes = 7 - len(paper_planes) if len(paper_planes) < 7 else 0

    # 홈 탭 메시지 구성
    await client.views_publish(
        user_id=user.user_id,
        view=View(
            type="home",
            blocks=[
                # 포인트 시스템 섹션
                HeaderBlock(
                    text="🍭 내 글또 포인트",
                ),
                SectionBlock(
                    text=f"현재 *{user.name[1:]}* 님이 획득한 총 포인트는 *{user_point_history.total_point} point* 입니다.",
                ),
                ContextBlock(
                    elements=[
                        TextObject(
                            type="mrkdwn",
                            text=f"다음 회차에 글을 제출하면 *100* {next_combo_point}point 를 얻을 수 있어요.",
                        ),
                    ],
                ),
                ActionsBlock(
                    elements=[
                        ButtonElement(
                            text="포인트 획득 내역 보기",
                            action_id="open_point_history_view",
                            value="open_point_history_view",
                        ),
                        ButtonElement(
                            text="포인트 획득 방법 알아보기",
                            action_id="open_point_guide_view",
                            value="open_point_guide_view",
                        ),
                    ],
                ),
                DividerBlock(),
                # 종이비행기 섹션
                HeaderBlock(
                    text="✈️ 종이비행기 보내기",
                ),
                ContextBlock(
                    elements=[
                        TextObject(
                            type="mrkdwn",
                            text=f"종이비행기는 글또 멤버에게 따뜻한 감사나 응원의 메시지를 보낼 수 있는 기능이에요.\n매주 토요일 0시에 7개가 충전되며, 한 주 동안 자유롭게 원하는 분께 보낼 수 있어요.\n*{user.name[1:]}* 님이 이번 주에 보낼 수 있는 종이비행기 수는 현재 *{remain_paper_planes}개* 입니다. 😊",
                        ),
                    ],
                ),
                ActionsBlock(
                    elements=[
                        ButtonElement(
                            text="종이비행기 보내기",
                            action_id="send_paper_plane_message",
                            value="send_paper_plane_message",
                            style="primary",
                        ),
                        ButtonElement(
                            text="주고받은 종이비행기 보기",
                            action_id="open_paper_plane_url",
                            url="https://geultto-paper-plane.vercel.app",
                        ),
                        ButtonElement(
                            text="어떤 내용을 보내면 좋을까요?",
                            action_id="open_paper_plane_guide_view",
                            value="open_paper_plane_guide_view",
                        ),
                    ],
                ),
                DividerBlock(),
                # 글 제출 내역 관리 섹션
                HeaderBlock(
                    text="📚 슬기로운 글또 생활",
                ),
                ContextBlock(
                    elements=[
                        TextObject(
                            type="mrkdwn",
                            text=f"*{user.name[1:]}* 님이 궁금해할만한 내용들을 모아봤어요.",
                        ),
                    ],
                ),
                ActionsBlock(
                    elements=[
                        ButtonElement(
                            text="내가 제출한 글 보기",
                            action_id="open_submission_history_view",
                            value="open_submission_history_view",
                        ),
                        ButtonElement(
                            text="내가 북마크한 글 보기",
                            action_id="open_bookmark_page_view",
                            value="open_bookmark_page_view",
                        ),
                        ButtonElement(
                            text="내 커피챗 인증 내역 보기",
                            action_id="open_coffee_chat_history_view",
                            value="open_coffee_chat_history_view",
                        ),
                        ButtonElement(
                            text="남아있는 예치금 보기",
                            action_id="open_deposit_view",
                            value="open_deposit_view",
                        ),
                        ButtonElement(
                            text="또봇 기능 살펴보기",
                            action_id="open_help_view",
                            value="open_help_view",
                        ),
                    ],
                ),
                DividerBlock(),
                HeaderBlock(
                    text="🍧 또봇 실험실",
                ),
                ContextBlock(
                    elements=[
                        TextObject(
                            type="mrkdwn",
                            text="새로운 기능을 만나보세요. 더 나은 또봇을 위해 여러분의 의견을 기다립니다.\n\nComing Soon...🙇‍♂️",
                        ),
                    ],
                ),
            ],
        ),
    )


async def open_point_history_view(
    ack: AsyncAck,
    body: ActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """포인트 히스토리를 조회합니다."""
    await ack()

    user_point_history = point_service.get_user_point(user_id=user.user_id)

    footer_blocks: list[Block] = []
    if user_point_history.total_point > 0:
        footer_blocks = [
            DividerBlock(),
            SectionBlock(
                text="포인트 획득 내역은 최근 20개까지만 표시됩니다.\n전체 내역을 확인하려면 아래 버튼을 눌러주세요.",
            ),
            ActionsBlock(
                elements=[
                    ButtonElement(
                        text="전체 내역 다운로드",
                        action_id="download_point_history",
                        value="download_point_history",
                        style="primary",
                    ),
                ],
            ),
        ]

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            title=f"{user_point_history.user.name}님의 포인트 획득 내역",
            close="닫기",
            blocks=[
                SectionBlock(
                    text=f"총 *{user_point_history.total_point} point* 를 획득하셨어요.",
                ),
                DividerBlock(),
                SectionBlock(text=user_point_history.point_history_text),
                *footer_blocks,
            ],
        ),
    )


async def download_point_history(
    ack: AsyncAck,
    body: ActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """포인트 히스토리를 CSV 파일로 다운로드합니다."""
    await ack()

    response = await client.conversations_open(users=user.user_id)
    dm_channel_id = response["channel"]["id"]

    user_point = point_service.get_user_point(user_id=user.user_id)
    if not user_point.point_histories:
        await client.chat_postMessage(
            channel=dm_channel_id, text="포인트 획득 내역이 없습니다."
        )
        return None

    # 사용자의 제출내역을 CSV 파일로 임시 저장 후 전송
    temp_dir = "temp/point_histories"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    temp_file_path = f"{temp_dir}/{user.name}-포인트-획득-내역.csv"
    with open(temp_file_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(
            csvfile,
            PointHistory.fieldnames(),
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows([each.model_dump() for each in user_point.point_histories])

    res = await client.files_upload_v2(
        channel=dm_channel_id,
        file=temp_file_path,
        initial_comment=f"<@{user.user_id}> 님의 포인트 획득 내역 입니다.",
    )

    await client.chat_postMessage(
        channel=dm_channel_id,
        text=f"<@{user.user_id}> 님의 <{res['file']['permalink']}|포인트 획득 내역> 입니다.",
    )

    # 임시로 생성한 CSV 파일을 삭제
    os.remove(temp_file_path)


async def open_point_guide_view(
    ack: AsyncAck,
    body: ActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """포인트 획득 방법을 조회합니다."""
    await ack()

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            title={"type": "plain_text", "text": "포인트 획득 방법"},
            close={"type": "plain_text", "text": "닫기"},
            blocks=[
                SectionBlock(
                    text={
                        "type": "mrkdwn",
                        "text": "포인트는 다음과 같은 방법으로 획득할 수 있어요.",
                    }
                ),
                DividerBlock(),
                # 글 제출 관련 포인트
                SectionBlock(
                    text={
                        "type": "mrkdwn",
                        "text": "*🏆 글 제출 관련 포인트*\n"
                        "*`글 제출하기`* - 글을 제출하면 기본 *100 포인트* 획득\n"
                        "*`추가 글 제출`* - 동일 회차에 글을 추가로 제출할 때마다 *10 포인트* 획득\n"
                        "*`회차 연속 제출 콤보`* - 꾸준히 작성하면 *??? 포인트* 획득(꽤 많아요)\n"
                        "*`코어 채널 순위`* - 코어 채널 제출 순서에 따라 1, 2, 3등 각각 *50/30/20 포인트* 획득",
                    }
                ),
                DividerBlock(),
                # 참여 관련 포인트
                SectionBlock(
                    text={
                        "type": "mrkdwn",
                        "text": "*🏡 참여 관련 포인트*\n"
                        "*`커피챗 인증`* - 커피챗을 인증하면 *50 포인트* 획득\n"
                        "*`빌리지 반상회 참여`* - 반상회 참여 시 *50 포인트* 획득(수동 지급)",
                    }
                ),
                DividerBlock(),
                # 큐레이션 관련 포인트
                SectionBlock(
                    text={
                        "type": "mrkdwn",
                        "text": "*✍️ 큐레이션 관련 포인트*\n"
                        "*`큐레이션 요청`* - 글 제출 시 큐레이션을 요청하면 *10 포인트* 획득\n"
                        "*`큐레이션 선정`* - 큐레이션에 선정되면 추가 *10 포인트* 획득(수동 지급)",
                    }
                ),
                DividerBlock(),
                # 공지사항 관련 포인트
                SectionBlock(
                    text={
                        "type": "mrkdwn",
                        "text": "*📢 공지사항 관련 포인트*\n"
                        "*`공지사항 이모지`* - 공지사항에 '공지확인' 이모지를 남기면 *10 포인트* 획득",
                    }
                ),
                DividerBlock(),
                # 자기소개 작성 포인트
                SectionBlock(
                    text={
                        "type": "mrkdwn",
                        "text": "*👋 자기소개 작성 포인트*\n"
                        "*`자기소개 작성하기`* - 자기소개 작성 시 *100 포인트* 획득(수동 지급)",
                    }
                ),
                DividerBlock(),
                # 기타 지급 포인트
                SectionBlock(
                    text={
                        "type": "mrkdwn",
                        "text": "*🎁 기타 지급 포인트*\n"
                        "*`기타 지급`* - 공지사항에 공유해드려요.",
                    }
                ),
            ],
        ),
    )


async def send_paper_plane_message(
    ack: AsyncAck,
    body: ActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """종이비행기 메시지를 전송합니다."""
    await ack()

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            title="종이비행기 보내기",
            callback_id="send_paper_plane_message_view",
            close="닫기",
            submit="보내기",
            blocks=[
                SectionBlock(
                    text="종이비행기로 전하고 싶은 마음을 적어주세요.",
                ),
                InputBlock(
                    block_id="paper_plane_receiver",
                    label="받는 사람",
                    element=UserSelectElement(
                        action_id="select_user",
                        placeholder="받는 사람을 선택해주세요.",
                    ),
                ),
                InputBlock(
                    block_id="paper_plane_message",
                    label="메시지",
                    element=PlainTextInputElement(
                        action_id="paper_plane_message",
                        placeholder="종이비행기로 전할 마음을 적어주세요.",
                        multiline=True,
                    ),
                ),
            ],
        ),
    )


async def send_paper_plane_message_view(
    ack: AsyncAck,
    body: ViewBodyType,
    client: AsyncWebClient,
    view: ViewType,
    say: AsyncSay,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """종이비행기 메시지를 전송합니다."""
    values = body["view"]["state"]["values"]
    receiver_id = values["paper_plane_receiver"]["select_user"]["selected_user"]
    text = values["paper_plane_message"]["paper_plane_message"]["value"]

    if user.user_id == receiver_id:
        await ack(
            response_action="errors",
            errors={
                "paper_plane_receiver": "종이비행기는 자신에게 보낼 수 없어요~😉",
            },
        )
        return

    paper_planes = service.fetch_current_week_paper_planes(user_id=user.user_id)
    if len(paper_planes) >= 7:
        await ack(
            response_action="errors",
            errors={
                "paper_plane_receiver": "종이비행기는 매주 7개까지만 보낼 수 있어요~😉",
            },
        )
        return

    await ack()

    receiver = service.get_user(user_id=receiver_id)
    service.create_paper_plane(
        sender=user,
        receiver=receiver,
        text=text,
    )

    await client.chat_postMessage(
        channel=settings.THANKS_CHANNEL,
        text=f"💌 *<@{receiver_id}>* 님에게 종이비행기가 도착했어요!😊",
        blocks=[
            SectionBlock(
                text=f"💌 *<@{receiver_id}>* 님에게 종이비행기가 도착했어요!\n\n",
            ),
            ContextBlock(
                elements=[
                    MarkdownTextObject(
                        text=">받은 종이비행기는 `/종이비행기` 명령어 -> [주고받은 종이비행기 보기] 를 통해 확인할 수 있어요."
                    )
                ],
            ),
        ],
    )

    await client.chat_postMessage(
        channel=user.user_id,
        text=f"💌 *<@{receiver_id}>* 님에게 종이비행기를 보냈어요!😊",
        blocks=[
            SectionBlock(
                text=f"💌 *<@{receiver_id}>* 님에게 종이비행기를 보냈어요!\n\n",
            ),
            ContextBlock(
                elements=[
                    MarkdownTextObject(
                        text=">보낸 종이비행기는 `/종이비행기` 명령어 -> [주고받은 종이비행기 보기] 를 통해 확인할 수 있어요."
                    )
                ],
            ),
        ],
    )


async def open_paper_plane_url(
    ack: AsyncAck,
    body: ActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """종이비행기 페이지를 엽니다."""
    # 해당 이벤트는 로그를 위해 ack만 수행합니다.
    await ack()


async def open_paper_plane_guide_view(
    ack: AsyncAck,
    body: ActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """종이비행기 사용 방법을 조회합니다."""
    await ack()

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            title={"type": "plain_text", "text": "종이비행기 사용 방법"},
            close={"type": "plain_text", "text": "닫기"},
            blocks=[
                # 사용 방법 안내
                SectionBlock(
                    text={
                        "type": "mrkdwn",
                        "text": "*✍️ 어떤 내용을 보내면 좋을까요?*\n"
                        "종이비행기 메시지를 작성할 때는 아래 내용을 참고해보세요. 😉\n\n"
                        "*`구체적인 상황`* - 어떤 활동이나 대화에서 고마움을 느꼈는지 이야기해요.\n"
                        "*`구체적인 내용`* - 그 사람이 어떤 도움을 줬거나, 어떤 말을 해줬는지 적어보세요.\n"
                        "*`효과와 감사 표현`* - 그 행동이 나에게 어떤 영향을 주었는지, 얼마나 감사한지 표현해요.\n"
                        "*`앞으로의 기대`* - 앞으로도 계속 함께해주길 바라는 마음을 전해보세요!",
                    }
                ),
                DividerBlock(),
                # 예시 메시지
                SectionBlock(
                    text={
                        "type": "mrkdwn",
                        "text": "*💌 종이비행기 메시지 예시*\n",
                    }
                ),
                # 예시 1: 스터디 활동
                ContextBlock(
                    elements=[
                        {
                            "type": "mrkdwn",
                            "text": '예시 1: 스터디 활동\n>"00 스터디에서 항상 열정적으로 참여해주셔서 정말 감사해요! 덕분에 저도 더 열심히 하게 되고, 많은 배움을 얻고 있어요. 앞으로도 함께 성장해나갈 수 있으면 좋겠어요! 😊"',
                        }
                    ]
                ),
                # 예시 2: 커피챗 대화
                ContextBlock(
                    elements=[
                        {
                            "type": "mrkdwn",
                            "text": '예시 2: 커피챗 대화\n>"지난번 커피챗에서 나눈 대화가 정말 인상 깊었어요. 개발에 대한 생각을 나누고 조언을 주셔서 고맙습니다! 다음에도 또 이런 기회가 있으면 좋겠네요!"',
                        }
                    ]
                ),
                # 예시 3: 반상회 발표
                ContextBlock(
                    elements=[
                        {
                            "type": "mrkdwn",
                            "text": '예시 3: 반상회 발표\n>"최근 반상회에서 발표하신 모습이 인상적이었어요! 멀리서 지켜보면서 많은 영감을 받았답니다. 😊 나중에 기회가 된다면 커피챗으로 더 깊게 이야기를 나눌 수 있으면 좋겠어요!"',
                        }
                    ]
                ),
                DividerBlock(),
                # 가이드 마무리
                SectionBlock(
                    text={
                        "type": "mrkdwn",
                        "text": "이렇게 진심을 담은 메시지를 종이비행기에 담아 전달해보세요! ✈️",
                    }
                ),
            ],
        ),
    )


async def open_coffee_chat_history_view(
    ack: AsyncAck,
    body: ActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """커피챗 히스토리를 조회합니다."""
    await ack()

    coffee_chat_proofs = service.fetch_coffee_chat_proofs(user_id=user.user_id)

    blocks: list[Block] = []
    for proof in coffee_chat_proofs:
        blocks.append(SectionBlock(text=f"*{ts_to_dt(proof.ts).strftime('%Y-%m-%d')}*"))
        text = proof.text[:100] + " ..." if len(proof.text) >= 100 else proof.text
        blocks.append(ContextBlock(elements=[MarkdownTextObject(text=f"> {text}")]))

    footer_blocks = (
        [
            DividerBlock(),
            SectionBlock(
                text="커피챗 내역은 최근 10개까지만 표시됩니다.\n전체 내역을 확인하려면 아래 버튼을 눌러주세요.",
            ),
            ActionsBlock(
                elements=[
                    ButtonElement(
                        text="전체 내역 다운로드",
                        action_id="download_coffee_chat_history",
                        value="download_coffee_chat_history",
                        style="primary",
                    ),
                ],
            ),
        ]
        if blocks
        else []
    )

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            title=f"{user.name}님의 커피챗 인증 내역",
            close="닫기",
            blocks=(
                SectionBlock(
                    text=f"총 *{len(coffee_chat_proofs)}* 개의 커피챗 내역이 있어요.",
                ),
                DividerBlock(),
                *(
                    blocks[:20]
                    if blocks
                    else [SectionBlock(text="아직 커피챗 인증 내역이 없어요.")]
                ),
                *footer_blocks,
            ),
        ),
    )


async def download_coffee_chat_history(
    ack: AsyncAck,
    body: ActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """커피챗 히스토리를 CSV 파일로 다운로드합니다."""
    await ack()

    response = await client.conversations_open(users=user.user_id)
    dm_channel_id = response["channel"]["id"]

    proofs = service.fetch_coffee_chat_proofs(user_id=user.user_id)
    if not proofs:
        await client.chat_postMessage(
            channel=dm_channel_id, text="커피챗 인증 내역이 없습니다."
        )
        return None

    # 사용자의 제출내역을 CSV 파일로 임시 저장 후 전송
    temp_dir = "temp/coffee_chat_proofs"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    temp_file_path = f"{temp_dir}/{user.name}-커피챗-인증-내역.csv"
    with open(temp_file_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(
            csvfile,
            CoffeeChatProof.fieldnames(),
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows([each.model_dump() for each in proofs])

    res = await client.files_upload_v2(
        channel=dm_channel_id,
        file=temp_file_path,
        initial_comment=f"<@{user.user_id}> 님의 커피챗 인증 내역 입니다.",
    )

    await client.chat_postMessage(
        channel=dm_channel_id,
        text=f"<@{user.user_id}> 님의 <{res['file']['permalink']}|커피챗 인증 내역> 입니다.",
    )

    # 임시로 생성한 CSV 파일을 삭제
    os.remove(temp_file_path)


async def handle_channel_created(
    ack: AsyncAck,
    body: ChannelCreatedBodyType,
    client: AsyncWebClient,
):
    """공개 채널 생성 이벤트를 처리합니다."""
    await ack()

    channel_id = body["event"]["channel"]["id"]
    await client.conversations_join(channel=channel_id)
    await client.chat_postMessage(
        channel=settings.ADMIN_CHANNEL,
        text=f"새로 만들어진 <#{channel_id}> 채널에 또봇이 참여했습니다. 😋",
    )
