import re

from app.slack.components import static_select
from app.constants import MAX_PASS_COUNT, ContentCategoryEnum
from app.exception import BotException, ClientException
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.models.views import View
from slack_sdk.models.blocks import (
    Block,
    SectionBlock,
    InputBlock,
    PlainTextInputElement,
    ContextBlock,
    MarkdownTextObject,
    DividerBlock,
    OverflowMenuElement,
    Option,
    ActionsBlock,
    ButtonElement,
    StaticSelectElement,
    UrlInputElement,
)
from slack_bolt.async_app import AsyncAck, AsyncSay

from app import models
from app.slack.services.base import SlackService
from app.slack.services.point import PointService, send_point_noti_message
from app.slack.types import (
    ActionBodyType,
    BlockActionBodyType,
    CommandBodyType,
    OverflowActionBodyType,
    ViewBodyType,
    ViewType,
)
from app.utils import dict_to_json_str, json_str_to_dict
from app.config import settings


async def submit_command(
    ack: AsyncAck,
    body: CommandBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: models.User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """글 제출 시작"""
    await ack()
    callback_id = "submit_view"

    # 어드민 유저는 제출하는 곳에 메세지가 전송됩니다.
    private_metadata = (
        body["channel_id"] if user.user_id in settings.ADMIN_IDS else user.channel_id
    )

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            private_metadata=private_metadata,
            callback_id=callback_id,
            title="또봇",
            submit="제출",
            blocks=[
                SectionBlock(
                    block_id="required_section",
                    text=user.submission_guide_message,
                ),
                InputBlock(
                    block_id="content_url",
                    label="글 링크",
                    element=UrlInputElement(
                        action_id="url_text_input-action",
                        placeholder="노션 링크는 하단 '글 제목'을 필수로 입력해주세요.",
                    ),
                ),
                InputBlock(
                    block_id="category",
                    label="카테고리",
                    element=StaticSelectElement(
                        action_id="category_select",
                        placeholder="글의 카테고리를 선택해주세요.",
                        options=static_select.options(
                            [category.value for category in ContentCategoryEnum]
                        ),
                    ),
                ),
                InputBlock(
                    block_id="curation",
                    label="큐레이션",
                    element=StaticSelectElement(
                        action_id="curation_select",
                        placeholder="글을 큐레이션 대상에 포함할까요?",
                        options=[
                            Option(text="큐레이션 대상이 되고 싶어요!", value="Y"),
                            Option(text="아직은 부끄러워요~", value="N"),
                        ],
                    ),
                ),
                DividerBlock(),
                InputBlock(
                    block_id="tag",
                    label="태그",
                    optional=True,
                    element=PlainTextInputElement(
                        action_id="tags_input",
                        placeholder="태그1,태그2,태그3, ... ",
                        multiline=False,
                    ),
                ),
                InputBlock(
                    block_id="description",
                    label="하고 싶은 말",
                    optional=True,
                    element=PlainTextInputElement(
                        action_id="text_input",
                        placeholder="하고 싶은 말이 있다면 남겨주세요.",
                        multiline=True,
                    ),
                ),
                InputBlock(
                    block_id="manual_title_input",
                    label="글 제목(직접 입력)",
                    optional=True,
                    element=PlainTextInputElement(
                        action_id="title_input",
                        placeholder="'글 제목'을 직접 입력합니다.",
                        multiline=False,
                    ),
                ),
            ],
        ),
    )


async def submit_view(
    ack: AsyncAck,
    body: ViewBodyType,
    client: AsyncWebClient,
    view: ViewType,
    say: AsyncSay,
    user: models.User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """글 제출 완료"""
    # 슬랙 앱이 구 버전일 경우 일부 block 이 사라져 키에러가 발생할 수 있음
    content_url = view["state"]["values"]["content_url"]["url_text_input-action"][
        "value"
    ]
    channel_id = view["private_metadata"]
    username = body["user"]["username"]
    is_submit = user.is_submit

    try:
        service.validate_url(view, content_url)
        title = await service.get_title(view, content_url)
    except (ValueError, ClientException) as e:
        await ack(response_action="errors", errors={"content_url": str(e)})
        raise e

    # 참고: ack 로 에러를 반환할 경우, 그전에 ack() 를 호출하지 않아야 한다.
    await ack()

    try:
        content = await service.create_submit_content(
            title,
            content_url,
            username,
            view,  # type: ignore # TODO: 원자 값을 넘기도록 수정
        )

        # 해당 text 는 슬랙 활동 탭에서 표시되는 메시지이며, 누가 어떤 링크를 제출했는지 확인합니다. (alt_text 와 유사한 역할)
        text = f"*<@{content.user_id}>님 제출 완료.* 링크 : *<{content.content_url}|{re.sub('<|>', '', title if content.title != 'title unknown.' else content.content_url)}>*"
        message = await client.chat_postMessage(
            channel=channel_id,
            text=text,
            blocks=[
                SectionBlock(text=service.get_chat_message(content)),
                ActionsBlock(
                    elements=[
                        ButtonElement(
                            text="자기소개 보기",
                            action_id="intro_modal",
                            value=content.user_id,
                        ),
                        ButtonElement(
                            text="이전 작성글 보기",
                            action_id="contents_modal",
                            value=content.user_id,
                        ),
                        ButtonElement(
                            text="북마크 추가📌",
                            action_id="bookmark_modal",
                            value=dict_to_json_str(
                                {
                                    "user_id": content.user_id,
                                    "dt": content.dt,
                                }
                            ),
                        ),
                    ],
                ),
            ],
        )
        content.ts = message.get("ts", "")

        await service.update_user_content(content)

    except Exception as e:
        message = f"{user.name}({user.channel_name}) 님의 제출이 실패했어요. {str(e)}"  # type: ignore
        raise BotException(message)  # type: ignore

    # 포인트 지급 1. 글 제출 시 포인트 지급
    submission_point_msg, is_additional = point_service.grant_if_post_submitted(
        user_id=content.user_id, is_submit=is_submit
    )
    await send_point_noti_message(
        client=client,
        channel=content.user_id,
        text=submission_point_msg,
    )

    # 추가 제출의 경우 연속 콤보, 채널 랭킹 포인트 지급을 하지 않는다.
    if not is_additional:
        # 포인트 지급 2.
        combo_point_msg = point_service.grant_if_post_submitted_continuously(
            user_id=content.user_id
        )
        if combo_point_msg:
            await send_point_noti_message(
                client=client,
                channel=content.user_id,
                text=combo_point_msg,
            )

        # 포인트 지급 3.
        ranking_point_msg = (
            point_service.grant_if_post_submitted_to_core_channel_ranking(
                user_id=content.user_id
            )
        )
        if ranking_point_msg:
            await send_point_noti_message(
                client=client,
                channel=content.user_id,
                text=ranking_point_msg,
            )

    if content.curation_flag == "Y":
        # 포인트 지급 4. 큐레이션 대상 글 제출 시 포인트 지급
        curation_point_msg = point_service.grant_if_curation_requested(
            user_id=content.user_id
        )
        await send_point_noti_message(
            client=client,
            channel=content.user_id,
            text=curation_point_msg,
        )


# TODO: 방학기간에 담소에도 글을 보낼지에 대한 메시지 전송 로직
# async def forward_message(
#     ack: AsyncAck,
#     body: ActionBodyType,
#     client: AsyncWebClient,
#     service: SlackService,
#     point_service: PointService,
# ) -> None:
#     await ack()

#     content_ts = body["actions"][0]["value"]
#     source_channel = body["channel"]["id"]
#     # target_channel = "C05J4FGB154"  # 자유로운 담소 채널 ID 테스트용
#     target_channel = "C0672HTT36C"  # 자유로운 담소 채널 ID 운영용

#     permalink_response = await client.chat_getPermalink(
#         channel=source_channel, message_ts=content_ts
#     )
#     permalink = permalink_response["permalink"]
#     content = service.get_content_by(ts=content_ts)

#     # 담소 채널에 보내는 메시지
#     text = f"<@{content.user_id}>님이 글을 공유했어요! \n👉 *<{permalink}|{content.title}>*"
#     await client.chat_postMessage(channel=target_channel, text=text)

#     # 나에게만 표시 메시지 수정하는 요청(slack bolt 에서는 지원하지 않음)
#     requests.post(
#         body["response_url"],
#         json={
#             "response_type": "ephemeral",
#             "text": f"<#{target_channel}> 에 전송되었어요. 📨",
#             "replace_original": True,
#             # "delete_original": True, # 삭제도 가능
#         },
#     )


async def open_intro_modal(
    ack: AsyncAck,
    body: ActionBodyType,
    client: AsyncWebClient,
    user: models.User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """다른 유저의 자기소개 확인"""
    await ack()

    other_user_id = body["actions"][0]["value"]
    other_user = service.get_user(other_user_id)
    intro_text = other_user.intro.replace("\\n", "\n") or "자기소개가 비어있어요. 😢"

    is_self = user.user_id == other_user_id

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            title=f"{other_user.name}님의 소개",
            submit="자기소개 수정" if is_self else None,
            callback_id="edit_intro_view" if is_self else None,
            close="닫기",
            blocks=[SectionBlock(text=intro_text)],
        ),
    )


async def edit_intro_view(
    ack: AsyncAck,
    body: ViewBodyType,
    client: AsyncWebClient,
    view: ViewType,
    say: AsyncSay,
    user: models.User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """자기소개 수정 시작"""
    await ack(
        response_action="update",
        view=View(
            type="modal",
            callback_id="submit_intro_view",
            title="자기소개 수정",
            submit="자기소개 제출",
            close="닫기",
            blocks=[
                SectionBlock(text="자신만의 개성있는 소개문구를 남겨주세요. 😉"),
                InputBlock(
                    block_id="description",
                    label="자기소개 내용",
                    optional=True,
                    element=PlainTextInputElement(
                        action_id="edit_intro",
                        multiline=True,
                        max_length=2000,
                        placeholder={
                            "type": "plain_text",
                            "text": f"{user.intro[:100]} ... ",
                        },
                    ),
                ),
            ],
        ),
    )


async def submit_intro_view(
    ack: AsyncAck,
    body: ViewBodyType,
    client: AsyncWebClient,
    view: ViewType,
    say: AsyncSay,
    user: models.User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """자기소개 수정 완료"""
    new_intro = view["state"]["values"]["description"]["edit_intro"]["value"] or ""
    service.update_user_intro(user.user_id, new_intro=new_intro)

    await ack(
        {
            "response_action": "update",
            "view": {
                "type": "modal",
                "callback_id": "submit_intro_view",
                "title": {"type": "plain_text", "text": "자기소개 수정 완료"},
                "close": {"type": "plain_text", "text": "닫기"},
                "blocks": [
                    {
                        "type": "image",
                        "image_url": "https://media1.giphy.com/media/g9582DNuQppxC/giphy.gif",  # noqa E501
                        "alt_text": "success",
                    },
                    {
                        "type": "rich_text",  # rich_text 는 블록 객체로 사용할 수 없음
                        "elements": [
                            {
                                "type": "rich_text_section",
                                "elements": [
                                    {
                                        "type": "text",
                                        "text": "자기소개 수정이 완료되었습니다. 👏🏼👏🏼👏🏼\n다시 [자기소개 보기] 버튼을 눌러 확인해보세요!",  # noqa E501
                                    }
                                ],
                            }
                        ],
                    },
                ],
            },
        }
    )


async def contents_modal(
    ack: AsyncAck,
    body: ActionBodyType,
    client: AsyncWebClient,
    service: SlackService,
    point_service: PointService,
) -> None:
    """다른 유저의 제출한 글 목록 확인"""
    await ack()

    other_user_id = body["actions"][0]["value"]
    other_user = service.get_user(other_user_id)

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            title=f"{other_user.name}님의 작성글",
            close="닫기",
            blocks=_fetch_blocks(other_user.contents),
        ),
    )


async def bookmark_modal(
    ack: AsyncAck,
    body: BlockActionBodyType | OverflowActionBodyType,
    client: AsyncWebClient,
    user: models.User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """북마크 저장 시작"""
    await ack()

    # TODO: 글 검색에서 넘어온 경우 북마크 저장 후 검색 모달로 돌아가야 함

    actions = body["actions"][0]
    is_overflow = actions["type"] == "overflow"  # TODO: 분리필요
    if is_overflow:
        content_value = json_str_to_dict(actions["selected_option"]["value"])  # type: ignore
    else:
        content_value = json_str_to_dict(actions["value"])  # type: ignore

    content = service.get_content_by(
        user_id=content_value["user_id"],
        dt=content_value["dt"],
    )
    bookmark = service.get_bookmark(user.user_id, content.ts)
    if bookmark is not None:
        # 이미 북마크가 되어 있다면 사용자에게 알린다.
        view = View(
            type="modal",
            title="북마크",
            close="닫기",
            blocks=[SectionBlock(text="\n이미 북마크한 글이에요. 😉")],
        )
    else:
        view = View(
            type="modal",
            private_metadata=dict_to_json_str(
                {
                    "content_user_id": content.user_id,
                    "content_ts": content.ts,
                }
            ),
            callback_id="bookmark_view",
            title="북마크",
            submit="북마크 추가",
            blocks=[
                SectionBlock(
                    block_id="required_section",
                    text="\n북마크한 글은 `/북마크` 명령어로 확인할 수 있어요.",
                ),
                InputBlock(
                    block_id="bookmark_note",
                    label="메모",
                    optional=True,
                    element=PlainTextInputElement(
                        action_id="text_input",
                        placeholder="북마크에 대한 메모를 남겨주세요.",
                        multiline=True,
                    ),
                ),
            ],
        )

    if is_overflow:
        await client.views_update(view_id=body["view"]["id"], view=view)  # type: ignore
    else:
        await client.views_open(trigger_id=body["trigger_id"], view=view)


async def create_bookmark_view(
    ack: AsyncAck,
    body: ViewBodyType,
    client: AsyncWebClient,
    view: ViewType,
    say: AsyncSay,
    user: models.User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """북마크 저장 완료"""
    await ack()

    private_metadata = json_str_to_dict(view["private_metadata"])
    content_user_id = private_metadata["content_user_id"]
    content_ts = private_metadata["content_ts"]

    value = view["state"]["values"]["bookmark_note"]["text_input"]["value"]
    note = value if value else ""  # 유저가 입력하지 않으면 None 으로 전달 된다.
    service.create_bookmark(
        user_id=user.user_id,
        content_user_id=content_user_id,
        content_ts=content_ts,
        note=note,
    )

    await ack(
        response_action="update",
        view=View(
            type="modal",
            title="북마크",
            close="닫기",
            blocks=[SectionBlock(text="\n북마크를 추가했어요. 😉")],
        ),
    )


async def pass_command(
    ack: AsyncAck,
    body: CommandBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: models.User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """글 패스 시작"""
    await ack()

    round, due_date = user.get_due_date()
    user.check_pass()

    # 어드민 유저는 제출하는 곳에 메세지가 전송됩니다.
    private_metadata = (
        body["channel_id"] if user.user_id in settings.ADMIN_IDS else user.channel_id
    )

    if user.is_submit:
        await client.views_open(
            trigger_id=body["trigger_id"],
            view=View(
                type="modal",
                title="패스",
                close="닫기",
                blocks=[
                    SectionBlock(
                        text=f"🤗 {user.name} 님은 이미 {round}회차 (마감일: {due_date}) 글을 제출했어요.\n`/제출내역` 명령어로 글 제출 내역을 확인해주세요."
                    )
                ],
            ),
        )

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=View(
            type="modal",
            private_metadata=private_metadata,
            callback_id="pass_view",
            title="또봇",
            submit="패스",
            blocks=[
                SectionBlock(
                    block_id="required_section",
                    text=f"패스 하려면 아래 '패스' 버튼을 눌러주세요.\
                        \n\n아래 유의사항을 확인해주세요.\
                        \n- 현재 회차는 {round}회차, 마감일은 {due_date} 이에요.\
                        \n- 패스는 연속으로 사용할 수 없어요.\
                        \n- 남은 패스는 {MAX_PASS_COUNT - user.pass_count}번 이에요.\
                        \n- 패스 메시지는 코어 채널인 <#{user.channel_id}> 채널에 표시됩니다.",
                ),
                InputBlock(
                    block_id="description",
                    optional=True,
                    label="하고 싶은 말",
                    element=PlainTextInputElement(
                        action_id="text_input",
                        placeholder="하고 싶은 말이 있다면 남겨주세요.",
                        multiline=True,
                    ),
                ),
            ],
        ),
    )


async def pass_view(
    ack: AsyncAck,
    body: ViewBodyType,
    client: AsyncWebClient,
    view: ViewType,
    say: AsyncSay,
    user: models.User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """글 패스 완료"""
    await ack()

    channel_id = view["private_metadata"]

    try:
        content = await service.create_pass_content(ack, body, view)
        message = await client.chat_postMessage(
            channel=channel_id,
            text=service.get_chat_message(content),
        )
        content.ts = message.get("ts", "")
        await service.update_user_content(content)
    except Exception as e:
        message = f"{user.name}({user.channel_name}) 님의 패스가 실패했어요. {str(e)}"  # type: ignore
        raise BotException(message)  # type: ignore


async def search_command(
    ack: AsyncAck,
    body: CommandBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    service: SlackService,
    point_service: PointService,
) -> None:
    """글 검색 시작"""
    await ack()

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=_get_search_view(),
    )


async def submit_search(
    ack: AsyncAck,
    body: ViewBodyType | ActionBodyType,
    client: AsyncWebClient,
    service: SlackService,
    point_service: PointService,
) -> None:
    """글 검색 완료"""
    name = _get_name(body)
    category = _get_category(body)
    keyword = _get_keyword(body)

    contents = service.fetch_contents(keyword, name, category)

    await ack(
        response_action="update",
        view=View(
            type="modal",
            callback_id="back_to_search_view",
            title=f"총 {len(contents)} 개의 글이 있어요. 🔍",
            submit="다시 검색",
            blocks=_fetch_blocks(contents),
        ),
    )


async def web_search(
    ack: AsyncAck,
    body: ActionBodyType,
    client: AsyncWebClient,
    service: SlackService,
    point_service: PointService,
) -> None:
    """웹 검색 시작(외부 링크로 이동)"""
    await ack()


def _fetch_blocks(contents: list[models.Content]) -> list[Block]:
    blocks: list[Block] = []
    blocks.append(SectionBlock(text="결과는 최대 20개까지만 표시해요."))
    for content in contents:

        if not content.content_url:
            # content_url 이 없는 경우는 패스이므로 제외
            continue

        blocks.append(DividerBlock())
        blocks.append(
            SectionBlock(
                text=f"*<{content.content_url}|{re.sub('<|>', '', content.title)}>*",
                accessory=OverflowMenuElement(
                    action_id="bookmark_modal",
                    options=[
                        Option(
                            text="북마크 추가📌",
                            value=dict_to_json_str(
                                {
                                    "user_id": content.user_id,
                                    "dt": content.dt,
                                }
                            ),
                        )
                    ],
                ),
            )
        )
        blocks.append(
            ContextBlock(
                elements=[
                    MarkdownTextObject(text=f"> 카테고리: {content.category}"),
                    MarkdownTextObject(
                        text=f"> 태그: {content.tags}" if content.tags else " "
                    ),
                ]
            )
        )
        if len(blocks) > 60:
            # 최대 60개의 블록만 반환
            # 그 이상은 Slack Modal 제한에 걸릴 수 있음
            return blocks
    return blocks


async def back_to_search_view(
    ack: AsyncAck,
    body: ViewBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    service: SlackService,
    point_service: PointService,
) -> None:
    """글 검색 다시 시작"""
    await ack(
        response_type="update",
        view=_get_search_view(),
    )


def _get_category(body):
    category = (
        body.get("view", {})
        .get("state", {})
        .get("values", {})
        .get("category_search", {})
        .get("chosen_category", {})
        .get("selected_option", {})
        .get("value", "전체")
    )
    return category


def _get_name(body) -> str:
    name = (
        body.get("view", {})
        .get("state", {})
        .get("values", {})
        .get("author_search", {})
        .get("author_name", {})
        .get("value", "")
    )
    return name


def _get_keyword(body) -> str:
    keyword = (
        body.get("view", {})
        .get("state", {})
        .get("values", {})
        .get("keyword_search", {})
        .get("keyword", {})
        .get("value", "")
    ) or ""
    return keyword


async def bookmark_command(
    ack: AsyncAck,
    body: CommandBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: models.User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """북마크 조회"""
    await ack()

    bookmarks = service.fetch_bookmarks(user.user_id)
    content_ids = [bookmark.content_ts for bookmark in bookmarks]
    contents = service.fetch_contents_by_ids(content_ids)
    content_matrix = _get_content_metrix(contents)

    view = View(
        type="modal",
        title=f"총 {len(contents)} 개의 북마크가 있어요.",
        blocks=_fetch_bookmark_blocks(content_matrix, bookmarks),
        callback_id="handle_bookmark_page_view",
        private_metadata=dict_to_json_str({"page": 1}),
    )

    if len(content_matrix) > 1:
        view.blocks.append(
            ActionsBlock(
                elements=[
                    ButtonElement(
                        text="다음 페이지",
                        style="primary",
                        action_id="next_bookmark_page_action",
                    )
                ]
            )
        )

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=view,
    )


async def bookmark_page_view(
    ack: AsyncAck,
    body: ActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: models.User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """북마크 조회"""
    await ack()

    bookmarks = service.fetch_bookmarks(user.user_id)
    content_ids = [bookmark.content_ts for bookmark in bookmarks]
    contents = service.fetch_contents_by_ids(content_ids)
    content_matrix = _get_content_metrix(contents)

    view = View(
        type="modal",
        title=f"총 {len(contents)} 개의 북마크가 있어요.",
        blocks=_fetch_bookmark_blocks(content_matrix, bookmarks),
        callback_id="handle_bookmark_page_view",
        private_metadata=dict_to_json_str({"page": 1}),
    )

    if len(content_matrix) > 1:
        view.blocks.append(
            ActionsBlock(
                elements=[
                    ButtonElement(
                        text="다음 페이지",
                        style="primary",
                        action_id="next_bookmark_page_action",
                    )
                ]
            )
        )

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=view,
    )


async def handle_bookmark_page(
    ack: AsyncAck,
    body: ViewBodyType | OverflowActionBodyType,
    say: AsyncSay,
    client: AsyncWebClient,
    user: models.User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """북마크 페이지 이동"""
    await ack()

    bookmarks = service.fetch_bookmarks(user.user_id)
    content_ids = [bookmark.content_ts for bookmark in bookmarks]
    contents = service.fetch_contents_by_ids(content_ids)
    content_matrix = _get_content_metrix(contents)
    action_id = body["actions"][0]["action_id"] if body.get("actions") else None  # type: ignore
    private_metadata = body.get("view", {}).get("private_metadata")
    page = json_str_to_dict(private_metadata).get("page", 1) if private_metadata else 1

    if action_id == "next_bookmark_page_action":
        page += 1
    elif action_id == "prev_bookmark_page_action":
        page -= 1

    view = View(
        type="modal",
        title=f"총 {len(contents)} 개의 북마크가 있어요.",
        blocks=_fetch_bookmark_blocks(content_matrix, bookmarks, page=page),
        callback_id="handle_bookmark_page_view",
        private_metadata=dict_to_json_str({"page": page}),
    )

    button_elements = []
    if page != 1:
        button_elements.append(
            ButtonElement(
                text="이전 페이지",
                style="primary",
                action_id="prev_bookmark_page_action",
            )
        )
    if len(content_matrix) > page:
        button_elements.append(
            ButtonElement(
                text="다음 페이지",
                style="primary",
                action_id="next_bookmark_page_action",
            )
        )

    if button_elements:
        view.blocks.append(ActionsBlock(elements=button_elements))

    if body["type"] == "block_actions":
        await client.views_update(
            view_id=body["view"]["id"],
            view=view,
        )
    else:
        await client.views_open(
            trigger_id=body["trigger_id"],
            view=view,
        )


def _fetch_bookmark_blocks(
    content_matrix: dict[int, list[models.Content]],
    bookmarks: list[models.Bookmark],
    page: int = 1,
) -> list[Block]:
    blocks: list[Block] = []
    blocks.append(SectionBlock(text=f"{len(content_matrix)} 페이지 중에 {page} 페이지"))
    for content in content_matrix.get(page, []):

        if not content.content_url:
            # content_url 이 없는 경우는 패스이므로 제외
            continue

        blocks.append(DividerBlock())
        blocks.append(
            SectionBlock(
                text=f"*<{content.content_url}|{re.sub('<|>', '', content.title)}>*",
                accessory=OverflowMenuElement(
                    action_id="bookmark_overflow_action",
                    options=[
                        Option(
                            value=dict_to_json_str(
                                {
                                    "action": "remove_bookmark",
                                    "content_ts": content.ts,
                                }
                            ),
                            text="북마크 취소📌",
                        ),
                        Option(
                            value=dict_to_json_str(
                                {
                                    "action": "view_note",
                                    "content_ts": content.ts,
                                }
                            ),
                            text="메모 보기✏️",
                        ),
                    ],
                ),
            )
        )

        note = [
            bookmark.note for bookmark in bookmarks if content.ts == bookmark.content_ts
        ][0]
        blocks.append(
            ContextBlock(elements=[MarkdownTextObject(text=f"\n> 메모: {note}")])
        )

        if len(blocks) > 60:
            # 최대 60개의 블록만 반환
            # 그 이상은 Slack Modal 제한에 걸릴 수 있음
            return blocks

    return blocks


async def open_overflow_action(
    ack: AsyncAck,
    body: OverflowActionBodyType,
    client: AsyncWebClient,
    say: AsyncSay,
    user: models.User,
    service: SlackService,
    point_service: PointService,
) -> None:
    """북마크 메뉴 선택"""
    await ack()

    title = ""
    text = ""
    value = json_str_to_dict(body["actions"][0]["selected_option"]["value"])
    if value["action"] == "remove_bookmark":
        title = "북마크 취소📌"
        service.update_bookmark(
            user.user_id,
            value["content_ts"],
            new_status=models.BookmarkStatusEnum.DELETED,
        )
        text = "북마크를 취소했어요."
    elif value["action"] == "view_note":
        title = "북마크 메모✏️"
        bookmark = service.get_bookmark(user.user_id, value["content_ts"])
        text = bookmark.note if bookmark and bookmark.note else "메모가 없어요."

    await client.views_update(
        view_id=body["view"]["id"],
        view=View(
            type="modal",
            callback_id="handle_bookmark_page_view",
            private_metadata=body["view"]["private_metadata"],  # example: {"page": 1}
            title=title,
            submit="돌아가기",
            blocks=[SectionBlock(text=text)],
        ),
    )


def _get_content_metrix(
    contents: list[models.Content], contents_per_page: int = 20
) -> dict[int, list[models.Content]]:
    """컨텐츠를 2차원 배열로 변환합니다."""

    content_matrix = {}
    for i, v in enumerate(range(0, len(contents), contents_per_page)):
        content_matrix.update({i + 1: contents[v : v + contents_per_page]})
    return content_matrix


def _get_search_view():
    return View(
        type="modal",
        callback_id="submit_search",
        title="글 검색 🔍",
        submit="검색",
        blocks=[
            SectionBlock(
                block_id="description_section",
                text="원하는 조건의 글을 검색할 수 있어요.",
            ),
            InputBlock(
                block_id="keyword_search",
                label="검색어",
                optional=True,
                element=PlainTextInputElement(
                    action_id="keyword",
                    placeholder="검색어를 입력해주세요.",
                    multiline=False,
                ),
            ),
            InputBlock(
                block_id="author_search",
                label="글 작성자",
                optional=True,
                element=PlainTextInputElement(
                    action_id="author_name",
                    placeholder="이름을 입력해주세요.",
                    multiline=False,
                ),
            ),
            InputBlock(
                block_id="category_search",
                label="카테고리",
                element=StaticSelectElement(
                    action_id="chosen_category",
                    placeholder="카테고리 선택",
                    initial_option=Option(value="전체", text="전체"),
                    options=static_select.options(
                        [category.value for category in ContentCategoryEnum] + ["전체"]
                    ),
                ),
            ),
            SectionBlock(
                text="웹으로 검색하시려면 [웹 검색] 버튼을 눌러주세요.",
                accessory=ButtonElement(
                    text="웹 검색",
                    action_id="web_search",
                    url="https://vvd.bz/d2HG",
                    style="primary",
                ),
            ),
        ],
    )
