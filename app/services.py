import datetime
import re
from app.client import SpreadSheetClient
from app.dto import Submission


class SubmissionService:
    def __init__(self, sheets_client: SpreadSheetClient) -> None:
        self._sheets_client = sheets_client
        self._url_regex = r"((http|https):\/\/)?[a-zA-Z0-9.-]+(\.[a-zA-Z]{2,})"

    async def open_modal(self, body, client, submit_view) -> None:
        await client.views_open(
            # Pass a valid trigger_id within 3 seconds of receiving it
            trigger_id=body["trigger_id"],
            # View payload
            view={
                "type": "modal",
                "private_metadata": body["channel_id"],
                # View identifier
                "callback_id": submit_view,
                "title": {"type": "plain_text", "text": "글똥이"},
                "submit": {"type": "plain_text", "text": "제출"},
                "blocks": [
                    {
                        "type": "section",
                        "block_id": "required_section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "글 쓰느라 고생 많았어~! 👏🏼👏🏼👏🏼\
                                \n[글 링크]와 [카테고리]를 입력하고 제출을 눌러줘~ 🥳",
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "content",
                        "element": {
                            "type": "url_text_input",
                            "action_id": "url_text_input-action",
                        },
                        "label": {"type": "plain_text", "text": "글 링크", "emoji": True},
                    },
                    {
                        "type": "input",
                        "block_id": "category",
                        "label": {"type": "plain_text", "text": "카테고리", "emoji": True},
                        "element": {
                            "type": "static_select",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "카테고리 선택",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "언어 & 기술",
                                        "emoji": True,
                                    },
                                    "value": "언어 & 기술",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "일상 & 관계",
                                        "emoji": True,
                                    },
                                    "value": "일상 & 관계",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "취준 & 이직",
                                        "emoji": True,
                                    },
                                    "value": "취준 & 이직",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "후기 & 회고",
                                        "emoji": True,
                                    },
                                    "value": "후기 & 회고",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "기타",
                                        "emoji": True,
                                    },
                                    "value": "기타",
                                },
                            ],
                            "action_id": "static_select-action",
                        },
                    },
                    {"type": "divider"},
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
                                "text": "남기고 싶은 말을 자유롭게 적어주세요",
                            },
                            "multiline": True,
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "남기고 싶은 말",
                            "emoji": True,
                        },
                    },
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
                                "text": "'회고,파이썬,생각, ... ' 처럼 콤마로 구분해서 적어주세요",
                            },
                            "multiline": False,
                        },
                    },
                ],
            },
        )

    async def get(self, ack, body, view) -> Submission:
        content_url = self._get_content_url(view)
        await self._validate_url(ack, content_url)
        submission = Submission(
            dt=datetime.datetime.strftime(datetime.datetime.now(), "%Y-%m-%d %H:%M:%S"),
            user_id=body["user"]["id"],
            username=body["user"]["username"],
            content_url=self._get_content_url(view),
            category=self._get_category(view),
            description=self._get_description(view),
            tag=self._get_tag(view),
        )
        return submission

    def submit(self, submission: Submission) -> None:
        self._sheets_client.submit(submission)

    async def send_chat_message(
        self, client, view, logger, submission: Submission
    ) -> None:
        tag_msg = self._get_tag_msg(submission.tag)
        description_msg = self._get_description_msg(submission.description)
        channal = view["private_metadata"]
        try:
            msg = f"\n<@{submission.user_id}>님 제출 완료🎉{description_msg}\
                \ncategory : {submission.category}{tag_msg}\
                \nlink : {submission.content_url}"
            await client.chat_postMessage(channel=channal, text=msg)
        except Exception as e:
            logger.exception(f"Failed to post a message {str(e)}")

    def _get_description(self, view) -> str:
        description = view["state"]["values"]["description"]["plain_text_input-action"][
            "value"
        ]
        if not description:
            description = ""
        return description

    def _get_tag(self, view) -> str:
        tag = ""
        raw_tag = view["state"]["values"]["tag"]["dreamy_input"]["value"]
        if raw_tag:
            tag = ",".join(tag for tag in raw_tag.split(",") if tag)
        return tag

    def _get_category(self, view) -> str:
        category = view["state"]["values"]["category"]["static_select-action"][
            "selected_option"
        ]["value"]

        return category

    def _get_content_url(self, view) -> str:
        content_url = view["state"]["values"]["content"]["url_text_input-action"][
            "value"
        ]
        return content_url

    def _get_description_msg(self, description) -> str:
        description_msg = ""
        if description:
            description_msg = f"\n\n💬 '{description}'\n"
        return description_msg

    def _get_tag_msg(self, tag) -> str:
        tag_msg = ""
        if tag:
            tags = tag.split(",")
            tag_msg = "\ntag : #" + " #".join(tags)
        return tag_msg

    async def _validate_url(self, ack, content_url) -> None:
        if not re.match(self._url_regex, content_url):
            errors = {}
            errors["content"] = "링크는 url 주소여야 합니다."
            await ack(response_action="errors", errors=errors)
            raise ValueError


class PassService:
    def __init__(self) -> None:
        ...

    async def open_modal(self) -> None:
        print("pass")
        ...


submission_service = SubmissionService(SpreadSheetClient())
pass_service = PassService()
