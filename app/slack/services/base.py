from datetime import datetime, timedelta
import random
import re
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from app.constants import URL_REGEX
from app.logging import logger
from app.exception import BotException, ClientException
from app.slack.repositories import SlackRepository
from app import models
from app import store
from app.constants import paper_plane_color_maps

from bs4 import BeautifulSoup

from app.utils import tz_now, tz_now_to_str


class SlackService:
    def __init__(self, repo: SlackRepository, user: models.User) -> None:
        self._repo = repo
        self._user = user

    def fetch_contents(
        self,
        keyword: str | None = None,
        name: str | None = None,
        category: str = "전체",
    ) -> list[models.Content]:
        """콘텐츠를 조건에 맞춰 가져옵니다."""
        if keyword:
            contents = self._repo.fetch_contents_by_keyword(keyword)
        else:
            contents = self._repo.fetch_contents()

        if name:
            user_ids = self._repo.fetch_user_ids_by_name(name)
            contents = [content for content in contents if content.user_id in user_ids]

        if category != "전체":
            contents = [content for content in contents if content.category == category]

        return contents

    def get_user(self, user_id) -> models.User:
        """유저와 콘텐츠 정보를 가져옵니다."""
        user = self._repo.get_user(user_id)
        if not user:
            raise BotException("해당 유저 정보가 없어요.")
        return user

    def get_only_user(self, user_id) -> models.User:
        """유저 정보만 가져옵니다."""
        user = self._repo.get_only_user(user_id)
        if not user:
            raise BotException("해당 유저 정보가 없어요.")
        return user

    async def create_submit_content(
        self,
        title: str,
        content_url: str,
        username: str,
        view: dict[str, Any],
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
            curation_flag=self._get_curation_flag(view),
        )
        return content

    async def update_user_content(self, content: models.Content) -> None:
        """유저의 콘텐츠를 업데이트합니다."""
        self._user.contents.append(content)
        self._repo.update(self._user)

    async def create_pass_content(self, ack, body, view) -> models.Content:
        """패스 콘텐츠를 생성합니다."""
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

    def _get_description(self, view) -> str:
        description: str = view["state"]["values"]["description"]["text_input"]["value"]
        if not description:
            return ""
        return description

    def _get_tags(self, view) -> str:
        raw_tag: str = view["state"]["values"]["tag"]["tags_input"]["value"]
        if not raw_tag:
            return ""
        deduplication_tags = list(dict.fromkeys(raw_tag.split(",")))
        tags = ",".join(tag.strip() for tag in deduplication_tags if tag)
        return tags

    def _get_category(self, view) -> str:
        category: str = view["state"]["values"]["category"]["category_select"][
            "selected_option"
        ]["value"]
        return category

    def _get_curation_flag(self, view) -> str:
        curation_flag: str = view["state"]["values"]["curation"]["curation_select"][
            "selected_option"
        ]["value"]
        return curation_flag

    async def get_title(self, view, url: str) -> str:

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                if response.status_code == 404:
                    raise ClientException(
                        f"비공개 글이거나, url을 찾을 수 없어요. 상태 코드 : {response.status_code}"
                    )
                if response.status_code >= 400:
                    raise ClientException(
                        f"url에 문제가 있어 확인이 필요해요. 상태 코드 : {response.status_code}"
                    )

            # 제목을 직접 입력한 경우에는 status_code만 확인 후에 return
            title_input = view["state"]["values"]["manual_title_input"]["title_input"][
                "value"
            ]
            if title_input:
                return title_input

            soup = BeautifulSoup(response.content, "html.parser", from_encoding="utf-8")
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
            "\n태그 : " + " ".join([f"`{t.strip()}`" for t in tag.split(",")])
            if tag
            else ""
        )
        return tag_message

    def validate_url(self, view, content_url: str) -> None:
        if not re.match(URL_REGEX, content_url):
            raise ValueError("링크는 url 형식이어야 해요.")
        if content_url in self._user.content_urls:
            raise ValueError("이미 제출한 url 이에요.")
        if "tistory.com/manage/posts" in content_url:
            # 티스토리 posts 페이지는 글 링크가 아니므로 제외합니다.
            raise ValueError("잠깐! 입력한 링크가 '글 링크'가 맞는지 확인해주세요.")
        if "blog.naver.com" in content_url and "redirect" in content_url.lower():
            # 네이버 블로그 리다이렉트 링크는 글 링크가 아니므로 제외합니다.
            raise ValueError(
                "잠깐! 입력한 링크는 리다이렉트 링크입니다. 다시 확인해주세요."
            )
        if (
            "notion." in content_url
            or "oopy.io" in content_url
            or ".site" in content_url
            or "blog.naver" in content_url
        ):
            # notion.so, notion.site, oopy.io 는 title 을 크롤링하지 못하므로 직접 입력을 받는다.
            # blog.naver 는 title 태그에 블로그 타이틀이 들어오기 때문에 글 제목을 직접 입력을 받는다.
            # 글 제목을 입력한 경우 통과.
            if (
                view["state"]["values"]
                .get("manual_title_input", {})
                .get("title_input", {})
                .get("value")
            ):
                return None
            raise ValueError(
                "노션 또는 네이버 링크는 하단 '글 제목'을 필수로 입력해주세요."
            )

    def create_bookmark(
        self,
        user_id: str,
        content_user_id: str,
        content_ts: str,
        note: str = "",
    ) -> models.Bookmark:
        """북마크를 생성합니다."""
        bookmark = models.Bookmark(
            user_id=user_id,
            content_user_id=content_user_id,
            content_ts=content_ts,
            note=note,
        )
        self._repo.create_bookmark(bookmark)
        store.bookmark_upload_queue.append(bookmark.to_list_for_sheet())
        return bookmark

    def get_bookmark(self, user_id: str, content_ts: str) -> models.Bookmark | None:
        """북마크를 가져옵니다."""
        bookmark = self._repo.get_bookmark(user_id, content_ts)
        return bookmark

    def fetch_bookmarks(self, user_id: str) -> list[models.Bookmark]:
        """유저의 북마크를 모두 가져옵니다."""
        # TODO: 키워드로 검색 기능 추가
        bookmarks = self._repo.fetch_bookmarks(user_id)
        return bookmarks

    def fetch_contents_by_ids(
        self, content_ids: list[str], keyword: str = ""
    ) -> list[models.Content]:
        """컨텐츠 아이디로 Contents 를 가져옵니다."""
        if keyword:
            contents = self._repo.fetch_contents_by_keyword(keyword)
        else:
            contents = self._repo.fetch_contents()
        return [content for content in contents if content.ts in content_ids]

    def update_bookmark(
        self,
        user_id: str,
        content_ts: str,
        new_note: str = "",
        new_status: models.BookmarkStatusEnum = models.BookmarkStatusEnum.ACTIVE,
    ) -> None:
        """북마크를 업데이트합니다."""
        # TODO: 북마크 삭제와 수정 분리할 것
        self._repo.update_bookmark(content_ts, new_note, new_status)
        bookmark = self._repo.get_bookmark(user_id, content_ts, status=new_status)
        if bookmark:
            store.bookmark_update_queue.append(bookmark)

    def update_user_intro(
        self,
        user_id: str,
        new_intro: str,
    ) -> None:
        """사용자의 자기소개를 수정합니다."""
        if self._user.user_id != user_id:
            raise BotException("본인의 자기소개만 수정할 수 있습니다.")
        self._repo.update_user_intro(user_id, new_intro)

    def fetch_users(self) -> list[models.User]:
        users = [models.User(**user) for user in self._repo._fetch_users()]
        return users

    def get_content_by(
        self,
        *,
        ts: str | None = None,
        user_id: str | None = None,
        dt: str | None = None,
    ) -> models.Content:
        content = self._repo.get_content_by(
            ts=ts,
            user_id=user_id,
            dt=dt,
        )
        if not content:
            raise BotException("해당 콘텐츠 정보가 없어요.")

        return content

    def fetch_coffee_chat_proofs(
        self,
        user_id: str,
    ) -> list[models.CoffeeChatProof]:
        """커피챗 인증 내역을 가져옵니다."""
        return self._repo.fetch_coffee_chat_proofs(user_id=user_id)

    def create_coffee_chat_proof(
        self,
        ts: str,
        thread_ts: str,
        user_id: str,
        text: str,
        files: list[dict[str, Any]],
        selected_user_ids: str,
        participant_call_thread_ts: str = "",
    ) -> models.CoffeeChatProof:
        """커피챗 인증글을 생성합니다."""
        try:
            image_urls = ",".join(file["url_private"] for file in files)
        except KeyError:
            image_urls = ""

        coffee_chat_proof = models.CoffeeChatProof(
            ts=ts,
            thread_ts=thread_ts,
            user_id=user_id,
            text=text,
            image_urls=image_urls,
            selected_user_ids=selected_user_ids,
            participant_call_thread_ts=participant_call_thread_ts,
        )
        self._repo.create_coffee_chat_proof(coffee_chat_proof)
        store.coffee_chat_proof_upload_queue.append(
            coffee_chat_proof.to_list_for_sheet()
        )
        return coffee_chat_proof

    def check_coffee_chat_proof(
        self,
        thread_ts: str,
        user_id: str,
    ) -> None:
        """
        커피챗 인증 가능 여부를 확인합니다.

        1. 스레드의 상위 메시지(thread_ts)로 기존 커피챗 인증 글(ts)이 존재하지 않으면, 인증할 수 없습니다.
        2. 인증 대상자 목록(selected_user_ids)에 해당 사용자의 user_id가 포함되어 있지 않으면, 인증할 수 없습니다.
        3. 동일한 user_id로 이미 커피챗 인증이 되어 있는 경우, 중복 인증을 할 수 없습니다.
        """
        parent_proof = self._repo.get_coffee_chat_proof(ts=thread_ts)
        if not parent_proof:
            raise BotException("커피챗 인증글을 찾을 수 없어요.")

        if user_id not in parent_proof.selected_user_ids:
            raise BotException("커피챗 인증 대상이 아니에요.")

        proofs = self._repo.fetch_coffee_chat_proofs(thread_ts=thread_ts)
        for proof in proofs:
            if proof.user_id == user_id:
                raise BotException("이미 답글로 커피챗을 인증했어요.")

    def create_paper_plane(
        self,
        *,
        sender: models.User,
        receiver: models.User,
        text: str,
    ) -> models.PaperPlane:
        """리액션을 생성합니다."""
        color_map = random.choice(paper_plane_color_maps)
        model = models.PaperPlane(
            sender_id=sender.user_id,
            sender_name=sender.name,
            receiver_id=receiver.user_id,
            receiver_name=receiver.name,
            text=text,
            text_color=color_map["text_color"],
            bg_color=color_map["bg_color"],
            color_label=color_map["color_label"],
        )
        self._repo.create_paper_plane(model)
        store.paper_plane_upload_queue.append(model.to_list_for_sheet())
        return model

    def fetch_current_week_paper_planes(
        self,
        user_id: str,
    ) -> list[models.PaperPlane]:
        """이번 주 종이비행기를 가져옵니다."""
        today = tz_now()

        # 지난주 토요일 00시 계산
        last_saturday = today - timedelta(days=(today.weekday() + 2) % 7)
        start_dt = last_saturday.replace(hour=0, minute=0, second=0, microsecond=0)

        # 이번주 금요일 23:59:59 계산
        this_friday = start_dt + timedelta(days=6)
        end_dt = this_friday.replace(hour=23, minute=59, second=59, microsecond=999999)

        paper_planes = []
        for plane in self._repo.fetch_paper_planes(sender_id=user_id):
            plane_created_ad = datetime.fromisoformat(plane.created_at).replace(
                tzinfo=ZoneInfo("Asia/Seoul")
            )
            if start_dt <= plane_created_ad <= end_dt:
                paper_planes.append(plane)

        return paper_planes

    def fetch_subscriptions_by_user_id(
        self,
        user_id: str,
    ) -> list[models.Subscription]:
        """유저의 구독 내역을 가져옵니다."""
        return self._repo.fetch_subscriptions_by_user_id(user_id)

    def fetch_subscriptions_by_target_user_id(
        self,
        target_user_id: str,
    ) -> list[models.Subscription]:
        """타겟 유저의 구독 내역을 가져옵니다."""
        return self._repo.fetch_subscriptions_by_target_user_id(target_user_id)

    def create_subscription(
        self, user_id: str, target_user_id: str, target_user_channel: str
    ) -> models.Subscription:
        """구독을 생성합니다."""
        subscription = models.Subscription(
            user_id=user_id,
            target_user_id=target_user_id,
            target_user_channel=target_user_channel,
        )
        self._repo.create_subscription(subscription)
        store.subscription_upload_queue.append(subscription.to_list_for_sheet())
        return subscription

    def get_subscription(self, subscription_id: str) -> models.Subscription | None:
        """구독을 가져옵니다."""
        return self._repo.get_subscription(subscription_id)

    def cancel_subscription(self, subscription_id: str) -> None:
        """구독을 취소합니다."""
        self._repo.cancel_subscription(subscription_id)
        subscription = self._repo.get_subscription(
            subscription_id, status=models.SubscriptionStatusEnum.CANCELED
        )
        if subscription:
            subscription.updated_at = tz_now_to_str()
            store.subscription_update_queue.append(subscription.model_dump())
