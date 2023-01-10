from app.dao import SpreadSheetsDao, sheets_Dao


class SlackService:
    def __init__(self, sheets_dao: SpreadSheetsDao) -> None:
        self._sheets_dao = sheets_dao

    async def submit(self):
        # TODO: 슬랙 로직 추가
        await self._sheets_dao.submit(1, 2, 3, 4, 5)

    async def submit_modal_open(self, body, client, submit_view):
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
                            "text": "글 쓰느라 고생 많았어~! 짝짝짝 👏🏼\n글 링크와 카테고리를 입력하고 제출 버튼을 누르면 완료! 🥳",
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

    async def pass_modal_open(self):
        print("pass")
        ...


slack_service = SlackService(sheets_Dao)
