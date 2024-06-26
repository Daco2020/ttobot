import asyncio
import re
from typing import Any

import httpx
from app.constants import URL_REGEX, ContentCategoryEnum
from app.logging import log_event, logger
from app.constants import MAX_PASS_COUNT
from app.slack.exception import BotException, ClientException
from app.slack.repositories import SlackRepository
from app.slack.components import static_select
from app.constants import remind_message
from app import models
from app import store

from bs4 import BeautifulSoup


from slack_bolt.async_app import AsyncApp


class SlackService:
    def __init__(self, user_repo: SlackRepository, user: models.User) -> None:
        self._user_repo = user_repo
        self._user = user

    @property
    def user(self) -> models.User:
        """유저를 가져옵니다."""
        return self._user

    def fetch_contents(
        self,
        keyword: str | None = None,
        name: str | None = None,
        category: str = "전체",
    ) -> list[models.Content]:
        """콘텐츠를 조건에 맞춰 가져옵니다."""
        if keyword:
            contents = self._user_repo.fetch_contents_by_keyword(keyword)
        else:
            contents = self._user_repo.fetch_contents()

        if name:
            user_ids = self._user_repo.fetch_user_ids_by_name(name)
            contents = [content for content in contents if content.user_id in user_ids]

        if category != "전체":
            contents = [content for content in contents if content.category == category]

        return contents

    def get_other_user(self, user_id) -> models.User:
        """다른 유저를 가져옵니다."""
        user = self._user_repo.get_user(user_id)
        return user  # type: ignore

    async def create_submit_content(
        self, title: str, content_url: str, username: str, view: dict[str, Any]
    ) -> models.Content:
        """제출 콘텐츠를 생성합니다."""
        content = models.Content(
            user_id=self._user.user_id,
            username=username,
            title=title,
            content_url=content_url,
            category=self._get_category(view),
            description=self._get_description(view),
            type="submit",
            tags=self._get_tags(view),
            # curation_flag=self._get_curation_flag(view), # TODO: 방학기간에는 제거, 10기에 활성화 필요
        )
        return content

    async def update_user_content(self, content: models.Content) -> None:
        """유저의 콘텐츠를 업데이트합니다."""
        self._user.contents.append(content)
        self._user_repo.update(self._user)

    async def create_pass_content(self, ack, body, view) -> models.Content:
        """패스 콘텐츠를 생성합니다."""
        await self._validate_pass()
        content = models.Content(
            user_id=body["user"]["id"],
            username=body["user"]["username"],
            description=self._get_description(view),
            type="pass",
        )
        return content

    def get_chat_message(self, content: models.Content) -> str:
        if content.type == "submit":
            title = content.title.replace("\n", " ")
            message = f"\n>>>🎉 *<@{content.user_id}>님 제출 완료.*\
                {self._description_message(content.description)}\
                \n링크 : *<{content.content_url}|{re.sub('<|>', '', title if content.title != 'title unknown.' else content.content_url)}>*\
                \n카테고리 : {content.category}\
                {self._tag_message(content.tags)}"  # noqa E501
        else:
            message = f"\n>>>🙏🏼 *<@{content.user_id}>님 패스 완료.*\
                {self._description_message(content.description)}"
        return message

    def get_submit_history(self) -> str:
        message = ""
        for content in self._user.fetch_contents():
            round = content.get_round()
            sumit_head = f"✅  {round}회차 제출"
            pass_head = f"▶️  {round}회차 패스"
            if content.type == "submit":
                message += f"\n{sumit_head}  |  "
                message += f"{content.dt}"
                message += f"\n:point_right::skin-tone-2: {content.title}\n"

                # 슬랙 모달은 3000자까지만 허용하기 때문에 url을 제외하여 문자 길이를 줄임.
                # message += f"*<{content.content_url}|{re.sub('<|>', '', content.title)}>*"

            else:
                message += f"\n{pass_head}  |  "
                message += f"{content.dt}\n"
        return message or "제출 내역이 없어요."

    async def open_submit_modal(self, body, client, view_name: str) -> None:
        """제출 모달을 띄웁니다."""
        self._check_channel(body["channel_id"])
        round, due_date = self._user.get_due_date()
        guide_message = f"\n\n현재 회차는 {round}회차, 마감일은 {due_date} 이에요."
        if self._user.is_submit:
            guide_message += f"\n({self._user.name} 님은 이미 {round}회차 글을 제출했어요)"
        else:
            guide_message += f"\n({self._user.name} 님은 아직 {round}회차 글을 제출하지 않았어요)"
        await client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "private_metadata": body["channel_id"],
                "callback_id": view_name,
                "title": {"type": "plain_text", "text": "또봇"},
                "submit": {"type": "plain_text", "text": "제출"},
                "blocks": [
                    {
                        "type": "section",
                        "block_id": "required_section",
                        "text": {
                            "type": "mrkdwn",
                            "text": guide_message,
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "content_url",
                        "element": {
                            "type": "url_text_input",
                            "action_id": "url_text_input-action",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "노션은 하단의 '글 제목'을 필수로 입력해주세요.",
                                "emoji": True,
                            },
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "글 링크",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "category",
                        "label": {
                            "type": "plain_text",
                            "text": "카테고리",
                            "emoji": True,
                        },
                        "element": {
                            "type": "static_select",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "글의 카테고리를 선택해주세요.",
                                "emoji": True,
                            },
                            "options": static_select.options(
                                [category.value for category in ContentCategoryEnum]
                            ),
                            "action_id": "static_select-category",
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "curation",
                        "label": {
                            "type": "plain_text",
                            "text": "큐레이션",
                            "emoji": True,
                        },
                        "element": {
                            "type": "static_select",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "글을 큐레이션 대상에 포함할까요?",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "큐레이션 대상이 되고 싶어요!",
                                        "emoji": True,
                                    },
                                    "value": "Y",  # str만 반환할 수 있음
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "아직은 부끄러워요~",
                                        "emoji": True,
                                    },
                                    "value": "N",
                                },
                            ],
                            "action_id": "static_select-curation",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "input",
                        "block_id": "tag",
                        "label": {
                            "type": "plain_text",
                            "text": "태그",
                        },
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "dreamy_input",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "태그1,태그2,태그3, ... ",
                            },
                            "multiline": False,
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "description",
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "plain_text_input-action",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "하고 싶은 말이 있다면 남겨주세요.",
                            },
                            "multiline": True,
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "하고 싶은 말",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "manual_title_input",
                        "label": {
                            "type": "plain_text",
                            "text": "글 제목(직접 입력)",
                        },
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "title_input",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "'글 제목'을 직접 입력합니다.",
                            },
                            "multiline": False,
                        },
                    },
                ],
            },
        )

    async def open_pass_modal(self, body, client, view_name: str) -> None:
        """패스 모달을 띄웁니다."""
        self._check_channel(body["channel_id"])
        await self._validate_pass()

        pass_count = self._user.pass_count
        round, due_date = self._user.get_due_date()

        if self._user.is_submit and self._user.channel_id != "ALL":
            await client.chat_postEphemeral(
                channel=self._user.channel_id,
                user=self._user.user_id,
                text=f"🤗 {self._user.name} 님은 이미 {round}회차(마감일: {due_date}) 글을 제출했어요. 제출내역을 확인해주세요.",  # noqa E501
            )
            return
        await client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "private_metadata": body["channel_id"],
                "callback_id": view_name,
                "title": {"type": "plain_text", "text": "또봇"},
                "submit": {"type": "plain_text", "text": "패스"},
                "blocks": [
                    {
                        "type": "section",
                        "block_id": "required_section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"패스 하려면 아래 '패스' 버튼을 눌러주세요.\
                            \n\n아래 유의사항을 확인해주세요.\
                            \n- 현재 회차는 {round}회차, 마감일은 {due_date} 이에요.\
                            \n- 패스는 연속으로 사용할 수 없어요.\
                            \n- 남은 패스는 {MAX_PASS_COUNT - pass_count}번 이에요.",
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "description",
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "plain_text_input-action",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "하고 싶은 말이 있다면 남겨주세요.",
                            },
                            "multiline": True,
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "하고 싶은 말",
                            "emoji": True,
                        },
                    },
                ],
            },
        )

    async def open_search_modal(self, body, client) -> dict[str, Any]:
        return await client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "submit_search",
                "title": {"type": "plain_text", "text": "글 검색 🔍"},
                "submit": {"type": "plain_text", "text": "검색"},
                "blocks": [
                    {
                        "type": "section",
                        "block_id": "description_section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "원하는 조건의 글을 검색할 수 있어요.",
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "keyword_search",
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "keyword",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "검색어를 입력해주세요.",
                            },
                            "multiline": False,
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "검색어",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "author_search",
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "author_name",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "이름을 입력해주세요.",
                            },
                            "multiline": False,
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "글 작성자",
                            "emoji": False,
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "category_search",
                        "label": {
                            "type": "plain_text",
                            "text": "카테고리",
                            "emoji": True,
                        },
                        "element": {
                            "type": "static_select",
                            "action_id": "chosen_category",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "카테고리 선택",
                            },
                            "initial_option": {
                                "text": {"type": "plain_text", "text": "전체"},
                                "value": "전체",
                            },
                            "options": static_select.options(
                                [category.value for category in ContentCategoryEnum] + ["전체"]
                            ),
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "웹으로 검색하시려면 [웹 검색] 버튼을 눌러주세요.",
                        },
                        "accessory": {
                            "type": "button",
                            "action_id": "web_search",
                            "text": {
                                "type": "plain_text",
                                "text": "웹 검색",
                            },
                            "url": "https://vvd.bz/d2HG",
                            "style": "primary",
                        },
                    },
                ],
            },
        )

    def _get_description(self, view) -> str:
        description: str = view["state"]["values"]["description"]["plain_text_input-action"][
            "value"
        ]
        if not description:
            return ""
        return description

    def _get_tags(self, view) -> str:
        raw_tag: str = view["state"]["values"]["tag"]["dreamy_input"]["value"]
        if not raw_tag:
            return ""
        deduplication_tags = list(dict.fromkeys(raw_tag.split(",")))
        tags = ",".join(tag.strip() for tag in deduplication_tags if tag)
        return tags

    def _get_category(self, view) -> str:
        category: str = view["state"]["values"]["category"]["static_select-category"][
            "selected_option"
        ]["value"]
        return category

    def _get_curation_flag(self, view) -> str:
        curation_flag: str = view["state"]["values"]["curation"]["static_select-curation"][
            "selected_option"
        ]["value"]
        return curation_flag

    async def get_title(self, view, url: str) -> str:

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                if response.status_code == 404:
                    raise ClientException("비공개 글이거나, url 를 찾을 수 없어요.")

            # 제목을 직접 입력한 경우에는 status_code만 확인 후에 return
            title_input = view["state"]["values"]["manual_title_input"]["title_input"]["value"]
            if title_input:
                return title_input

            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.find("title")
            if not title:
                raise ClientException(
                    "'글 제목'을 찾을 수 없습니다. 모달 하단에 직접 입력해주세요."
                )
            return title.text.strip()

        except ClientException as e:
            raise e
        except Exception as e:
            logger.debug(str(e))
            raise ClientException("url 에 문제가 있어요. 확인 후 다시 시도해주세요.")

    def _description_message(self, description: str) -> str:
        description_message = f"\n\n💬 '{description}'\n" if description else ""
        return description_message

    def _tag_message(self, tag: str) -> str:
        tag_message = (
            "\n태그 : " + " ".join([f"`{t.strip()}`" for t in tag.split(",")]) if tag else ""
        )
        return tag_message

    def _check_channel(self, channel_id) -> None:
        if self._user.channel_id == "ALL":
            return
        if self._user.channel_id != channel_id:
            raise BotException(
                f"{self._user.name} 님의 코어 채널 <#{self._user.channel_id}> 에서 다시 시도해주세요."
            )

    def validate_url(self, view, content_url: str) -> None:
        if not re.match(URL_REGEX, content_url):
            raise ValueError("링크는 url 형식이어야 해요.")
        if content_url in self._user.content_urls:
            raise ValueError("이미 제출한 url 이에요.")
        if "tistory.com/manage/posts" in content_url:
            # 티스토리 posts 페이지는 글 링크가 아니므로 제외합니다.
            raise ValueError("잠깐! 입력한 링크가 '글 링크'가 맞는지 확인해주세요.")
        if "notion." in content_url or "oopy.io" in content_url or ".site" in content_url:
            # notion.so, notion.site, oopy.io 는 title 을 크롤링하지 못하므로 직접 입력을 받는다.
            # 글 제목을 입력한 경우 통과.
            if (
                view["state"]["values"]
                .get("manual_title_input", {})
                .get("title_input", {})
                .get("value")
            ):
                return None
            raise ValueError("노션은 하단의 '글 제목'을 필수로 입력해주세요.")

    async def _validate_pass(self) -> None:
        if self._user.pass_count >= MAX_PASS_COUNT:
            message = "사용할 수 있는 pass 가 없어요."
            raise BotException(message)
        if self._user.is_prev_pass:
            message = "직전 회차에 pass 를 사용했기 때문에 연속으로 pass 를 사용할 수 없어요."
            raise BotException(message)

    def create_bookmark(self, user_id: str, content_id: str, note: str = "") -> models.Bookmark:
        """북마크를 생성합니다."""
        bookmark = models.Bookmark(user_id=user_id, content_id=content_id, note=note)
        self._user_repo.create_bookmark(bookmark)
        store.bookmark_upload_queue.append(bookmark.to_list_for_sheet())
        return bookmark

    def get_bookmark(self, user_id: str, content_id: str) -> models.Bookmark | None:
        """북마크를 가져옵니다."""
        bookmark = self._user_repo.get_bookmark(user_id, content_id)
        return bookmark

    def fetch_bookmarks(self, user_id: str) -> list[models.Bookmark]:
        """유저의 북마크를 모두 가져옵니다."""
        # TODO: 키워드로 검색 기능 추가
        bookmarks = self._user_repo.fetch_bookmarks(user_id)
        return bookmarks

    def fetch_contents_by_ids(
        self, content_ids: list[str], keyword: str = ""
    ) -> list[models.Content]:
        """컨텐츠 아이디로 Contents 를 가져옵니다."""
        if keyword:
            contents = self._user_repo.fetch_contents_by_keyword(keyword)
        else:
            contents = self._user_repo.fetch_contents()
        return [content for content in contents if content.content_id in content_ids]

    def update_bookmark(
        self,
        user_id: str,
        content_id: str,
        new_note: str = "",
        new_status: models.BookmarkStatusEnum = models.BookmarkStatusEnum.ACTIVE,
    ) -> None:
        """북마크를 업데이트합니다."""
        # TODO: 북마크 삭제와 수정 분리할 것
        self._user_repo.update_bookmark(content_id, new_note, new_status)
        bookmark = self._user_repo.get_bookmark(user_id, content_id, status=new_status)
        if bookmark:
            store.bookmark_update_queue.append(bookmark)

    def update_user(
        self,
        user_id: str,
        new_intro: str,
    ) -> None:
        """사용자의 자기소개를 수정합니다."""
        if self._user.user_id != user_id:
            raise BotException("본인의 자기소개만 수정할 수 있습니다.")
        self._user_repo.update_user(user_id, new_intro)

    def create_trigger_message(
        self,
        user_id: str,
        channel_id: str,
        trigger_word: str,
    ) -> models.TriggerMessage:
        """키워드 메시지를 생성합니다."""
        trigger_message = models.TriggerMessage(
            user_id=user_id,
            channel_id=channel_id,
            trigger_word=trigger_word,
        )
        self._user_repo.create_trigger_message(trigger_message)
        store.trigger_message_upload_queue.append(trigger_message.to_list_for_sheet())
        return trigger_message

    def fetch_trigger_messages(self, channel_id: str | None = None) -> list[models.TriggerMessage]:
        """키워드 메시지를 가져옵니다."""
        triggers = self._user_repo.fetch_trigger_messages()

        if not channel_id:
            return triggers

        return [tirgger for tirgger in triggers if tirgger.channel_id == channel_id]

    def get_trigger_message(self, channel_id: str, message: str) -> models.TriggerMessage | None:
        """채널과 단어가 일치하는 키워드를 조회합니다."""
        triggers = self._user_repo.fetch_trigger_messages()

        for tirgger in triggers:
            if channel_id == tirgger.channel_id and tirgger.trigger_word in message:
                return tirgger

        return None

    def create_archive_message(
        self,
        ts: str,
        channel_id: str,
        message: str,
        user_id: str,
        trigger_word: str,
        file_urls: list[str],
    ) -> models.ArchiveMessage:
        """아카이브 메시지를 생성합니다."""
        archive_message = models.ArchiveMessage(
            ts=ts,
            channel_id=channel_id,
            message=message,
            user_id=user_id,
            trigger_word=trigger_word,
            file_urls=",".join(file_urls),
        )
        self._user_repo.create_archive_message(archive_message)
        store.archive_message_upload_queue.append(archive_message.to_list_for_sheet())
        return archive_message

    def fetch_archive_messages(
        self, channel_id: str, trigger_word: str, user_id: str
    ) -> list[models.ArchiveMessage]:
        """아카이브 메시지를 가져옵니다."""
        return self._user_repo.fetch_archive_messages(channel_id, trigger_word, user_id)

    def update_archive_message(
        self,
        ts: str,
        channel_id: str,
        message: str,
        user_id: str,
        trigger_word: str,
        file_urls: list[str],
    ) -> bool:
        """아카이브 메시지를 수정 또는 생성합니다."""
        if archive_message := self._user_repo.get_archive_message(ts):
            self._user_repo.update_archive_message(ts, message)
            store.archive_message_update_queue.append(archive_message.to_list_for_sheet())
            is_created = False
        else:
            # 수정이 아닌, 기존 메시지에 키워드를 추가한 경우 새로 생성
            archive_message = models.ArchiveMessage(
                ts=ts,
                channel_id=channel_id,
                message=message,
                user_id=user_id,
                trigger_word=trigger_word,
                file_urls=",".join(file_urls),
            )
            self._user_repo.create_archive_message(archive_message)
            store.archive_message_upload_queue.append(archive_message.to_list_for_sheet())
            is_created = True

        return is_created

    def fetch_users(self) -> list[models.User]:
        users = [models.User(**user) for user in self._user_repo._fetch_users()]
        return users

    def get_content_by_ts(self, ts: str) -> models.Content:
        return self._user_repo.get_content_by_ts(ts)  # type: ignore


class SlackReminderService:
    def __init__(self, user_repo: SlackRepository) -> None:
        self._user_repo = user_repo

    async def send_reminder_message_to_user(self, slack_app: AsyncApp) -> None:
        """사용자에게 리마인드 메시지를 전송합니다."""
        users = self._user_repo.fetch_users()
        for user in users:
            if user.is_submit:
                continue
            if user.cohort == "8기":
                continue
            if user.channel_name == "슬랙봇":
                continue

            log_event(
                actor="slack_reminder_service",
                event="send_reminder_message_to_user",
                type="reminder",
                description=f"{user.name} 님에게 리마인드 메시지를 전송합니다.",
            )

            await slack_app.client.chat_postMessage(
                channel=user.user_id,
                text=remind_message.format(user_name=user.name),
            )
            await asyncio.sleep(1)
            # 슬랙은 메시지 전송을 초당 1개를 권장하기 때문에 1초 대기합니다.
            # 참고문서: https://api.slack.com/methods/chat.postMessage#rate_limiting
