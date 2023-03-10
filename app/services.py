import datetime
import re
from app.config import MAX_PASS_COUNT, URL_REGEX
from app.repositories import FileUserRepository, UserRepository
from app import models
from app.utils import now_dt, print_log


class UserContentService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    def get_user(self, user_id, channel_id) -> models.User:
        user = self._user_repo.get(user_id)
        self._validate_user(channel_id, user)
        return user  # type: ignore

    def update_user(self, user, content):
        user.contents.append(content)
        self._user_repo.update(user)

    async def open_submit_modal(self, body, client, view_name: str) -> None:
        try:
            self.get_user(body["user_id"], body["channel_id"])
        except ValueError as e:
            await self._open_error_modal(client, body, view_name, str(e))
            return None
        await self._open_submit_modal(client, body, view_name)

    async def create_submit_content(
        self, ack, body, view, user: models.User
    ) -> models.Content:
        content_url = self._get_content_url(view)
        await self._validate_url(ack, content_url, user)
        content = models.Content(
            dt=datetime.datetime.strftime(now_dt(), "%Y-%m-%d %H:%M:%S"),
            user_id=body["user"]["id"],
            username=body["user"]["username"],
            content_url=content_url,
            category=self._get_category(view),
            description=self._get_description(view),
            tags=self._get_tags(view),
            type="submit",
        )
        self.update_user(user, content)
        return content

    async def open_pass_modal(self, body, client, view_name: str) -> None:
        try:
            user = self.get_user(body["user_id"], body["channel_id"])
        except ValueError as e:
            await self._open_error_modal(client, body, view_name, str(e))
            return None
        await self._open_pass_modal(client, body, view_name, user.pass_count)

    async def create_pass_content(
        self, ack, body, view, user: models.User
    ) -> models.Content:
        await self._validate_pass(ack, user)
        content = models.Content(
            dt=datetime.datetime.strftime(now_dt(), "%Y-%m-%d %H:%M:%S"),
            user_id=body["user"]["id"],
            username=body["user"]["username"],
            description=self._get_description(view),
            type="pass",
        )
        self.update_user(user, content)
        return content

    def get_chat_message(self, content) -> str:
        if content.type == "submit":
            message = f"\n>>>???? *<@{content.user_id}>??? ?????? ??????.*\
                {self._description_message(content.description)}\
                \ncategory : {content.category}\
                {self._tag_message(content.tags)}\
                \nlink : {content.content_url}"
        else:
            message = f"\n>>>???????? *<@{content.user_id}>??? ?????? ??????.*\
                {self._description_message(content.description)}"
        return message

    def get_submit_history(self, user_id: str) -> str:
        user = self._user_repo.get(user_id)
        if user is None:
            return "????????? ????????? ????????????. [???????????????]????????? ??????????????????."
        return self._history_message(user)

    def validate_admin_user(self, user_id: str) -> None:
        if user_id not in ["U02HPESDZT3", "U04KVHPMQQ6"]:
            raise ValueError("????????? ????????? ????????????.")

    def _history_message(self, user: models.User) -> str:
        message = f"\n>>>????  *<@{user.user_id}> ?????? ?????? ???????????????!*\n"
        for content in user.fetch_contents():
            message += f"\n{'??? ??????' if content.type == 'submit' else '?????? ??????'}  |  "
            message += f"{content.dt}  |  "
            message += f"{content.content_url}"
        return message

    async def _open_error_modal(
        self, client, body: dict[str, str], view_name: str, e: str
    ) -> None:
        message = (
            f"{body.get('user_id')}({body.get('channel_id')}) ?????? {view_name} ??? ?????????????????????."
        )
        print_log(message, e)
        e = "????????? ?????? ????????? ?????????????????????.\n[???????????????] ????????? ??????????????????." if "Content" in e else e
        await client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "private_metadata": body["channel_id"],
                "callback_id": view_name,
                "title": {"type": "plain_text", "text": "??????"},
                "close": {"type": "plain_text", "text": "??????"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "plain_text",
                            "text": f"???? \n{e}",
                        },
                    }
                ],
            },
        )

    async def _open_submit_modal(self, client, body, view_name: str) -> None:
        await client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "private_metadata": body["channel_id"],
                "callback_id": view_name,
                "title": {"type": "plain_text", "text": "??????"},
                "submit": {"type": "plain_text", "text": "??????"},
                "blocks": [
                    {
                        "type": "section",
                        "block_id": "required_section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "??? ????????? ?????? ????????????~ ????????????????????????\n[??? ??????]??? [????????????]??? ??????????????????! ????",
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "content_url",
                        "element": {
                            "type": "url_text_input",
                            "action_id": "url_text_input-action",
                        },
                        "label": {"type": "plain_text", "text": "??? ??????", "emoji": True},
                    },
                    {
                        "type": "input",
                        "block_id": "category",
                        "label": {"type": "plain_text", "text": "????????????", "emoji": True},
                        "element": {
                            "type": "static_select",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "???????????? ??????",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "????????????",
                                        "emoji": True,
                                    },
                                    "value": "????????????",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "?????? & ??????",
                                        "emoji": True,
                                    },
                                    "value": "?????? & ??????",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "?????? & ??????",
                                        "emoji": True,
                                    },
                                    "value": "?????? & ??????",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "?????? & ??????",
                                        "emoji": True,
                                    },
                                    "value": "?????? & ??????",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "?????? & ??????",
                                        "emoji": True,
                                    },
                                    "value": "?????? & ??????",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "??????",
                                        "emoji": True,
                                    },
                                    "value": "??????",
                                },
                            ],
                            "action_id": "static_select-action",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "input",
                        "block_id": "description",
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "plain_text_input-action",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "?????? ?????? ?????? ????????? ???????????????.",
                            },
                            "multiline": True,
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "?????? ?????? ???",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "tag",
                        "label": {
                            "type": "plain_text",
                            "text": "??????",
                        },
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "dreamy_input",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "??????1,??????2,??????3, ... ",
                            },
                            "multiline": False,
                        },
                    },
                ],
            },
        )

    async def _open_pass_modal(
        self, client, body, view_name: str, pass_count: int
    ) -> None:
        await client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "private_metadata": body["channel_id"],
                "callback_id": view_name,
                "title": {"type": "plain_text", "text": "??????"},
                "submit": {"type": "plain_text", "text": "??????"},
                "blocks": [
                    {
                        "type": "section",
                        "block_id": "required_section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"?????? ????????? ?????? '??????' ????????? ???????????????.\
                            \n?????? ????????? {MAX_PASS_COUNT - pass_count}??? ????????????.\
                            \n????????? ???????????? ????????? ??? ?????????.",
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
                                "text": "?????? ?????? ?????? ????????? ???????????????.",
                            },
                            "multiline": True,
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "?????? ?????? ???",
                            "emoji": True,
                        },
                    },
                ],
            },
        )

    def _get_description(self, view) -> str:
        description: str = view["state"]["values"]["description"][
            "plain_text_input-action"
        ]["value"]
        if not description:
            description = ""
        return description

    def _get_tags(self, view) -> str:
        tags = ""
        raw_tag: str = view["state"]["values"]["tag"]["dreamy_input"]["value"]
        if raw_tag:
            deduplication_tags = list(
                dict.fromkeys(raw_tag.replace("#", "").split(","))
            )
            tags = ",".join(tag.strip() for tag in deduplication_tags if tag)
        return tags

    def _get_category(self, view) -> str:
        category: str = view["state"]["values"]["category"]["static_select-action"][
            "selected_option"
        ]["value"]

        return category

    def _get_content_url(self, view) -> str:
        # ?????? ?????? ??? ????????? ?????? ?????? block ??? ????????? ???????????? ????????? ??? ??????
        content_url: str = view["state"]["values"]["content_url"][
            "url_text_input-action"
        ]["value"]
        return content_url

    def _description_message(self, description: str) -> str:
        description_message = ""
        if description:
            description_message = f"\n\n???? '{description}'\n"
        return description_message

    def _tag_message(self, tag: str | None) -> str:
        tag_message = ""
        if tag:
            tag_message = "\ntag : " + " ".join(
                [f"`{tag.strip()}`" for tag in tag.split(",")]
            )
        return tag_message

    def _validate_user(self, channel_id, user: models.User | None) -> None:
        if not user:
            raise ValueError("????????? ????????? ???????????? ?????? ????????????.\n[???????????????] ????????? ??????????????????.")
        if user.channel_id != channel_id:
            raise ValueError(
                f"{user.name} ?????? ?????? ????????? [{user.channel_name}] ?????????.\
                             \n?????? ???????????? ?????? ??????????????????."
            )

    async def _validate_url(self, ack, content_url: str, user: models.User) -> None:
        if not re.match(URL_REGEX, content_url):
            block_id = "content_url"
            message = "????????? url ??????????????? ?????????."
            await ack(response_action="errors", errors={block_id: message})
            raise ValueError(message)
        if content_url in user.content_urls:
            block_id = "content_url"
            message = "?????? ????????? url ?????????."
            await ack(response_action="errors", errors={block_id: message})
            raise ValueError(message)

    async def _validate_pass(self, ack, user: models.User) -> None:
        if user.pass_count >= MAX_PASS_COUNT:
            block_id = "description"
            message = "????????? ??? ?????? pass ??? ????????????."
            await ack(response_action="errors", errors={block_id: message})
            raise ValueError(message)
        if user.before_type == "pass":
            block_id = "description"
            message = "???????????? pass ??? ????????? ??? ????????????."
            await ack(response_action="errors", errors={block_id: message})
            raise ValueError(message)


user_content_service = UserContentService(FileUserRepository())
