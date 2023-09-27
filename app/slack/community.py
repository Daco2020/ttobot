import loguru
from app.config import ANIMAL_TYPE
from app.services import user_content_service
from app.logging import event_log


async def guide_command(ack, body, logger, say, client, user_id: str) -> None:
    event_log(user_id, event="모코숲 가이드 조회")
    await ack()
    # await user_content_service.open_submit_modal(body, client, SUBMIT_VIEW)

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {
                "type": "plain_text",
                "text": "모여봐요 코드의 숲",
            },
            "close": {"type": "plain_text", "text": "닫기"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "글쓰기를 좋아하는 동물들이 코드의 숲에 모였다?\n우리가 함께 만들어 갈 여름 이야기, 모여봐요 코드의 숲! 🍃\n\n\n*설명*\n- 기존 2주 1글쓰기 규칙을 유지해요.\n- ‘모코숲’ 채널에 함께 모여 활동해요.\n- ‘모코숲’ 채널에 들어오면 자신이 어떤 동물인지 알 수 있어요.\n- 글만 올리면 심심하죠? 수다와 각종 모임 제안도 가능(권장)해요!\n\n\n*일정*\n- 7월 23일 일요일 ‘모코숲’이 열려요!\n- 7월 23일부터 9월 24일까지 두 달간 진행합니다.\n- 첫 번째 글 마감은 7월 30일 이에요! (이후 2주 간격 제출)\n\n\n*동물 소개*\n- 🐈 '고양이'는 여유롭고 독립된 일상을 즐겨요.\n- 🦦 '해달'은 기술과 도구에 관심이 많고 문제해결을 좋아해요.\n- 🦫 '비버'는 명확한 목표와 함께 협업을 즐겨요.\n- 🐘 '코끼리'는 커리어에 관심이 많고 자부심이 넘쳐요.\n- 🐕 '강아지'는 조직문화에 관심이 많고 팀워크를 중요하게 여겨요.\n- 🐢 '거북이'는 늦게 시작했지만 끝까지 포기하지 않아요.",  # noqa E501
                    },
                }
            ],
        },
    )


async def send_welcome_message(event, say, user_id: str):
    if event["channel"] == "C05K0RNQZA4":
        event_log(user_id, event="모코숲 채널 입장")
        try:
            user_id = event["user"]
            user = user_content_service.get_user_not_valid(user_id)
            animal = ANIMAL_TYPE[user.animal_type]

            message = (
                f"\n>>>{animal['emoji']}{animal['name']} <@{user_id}>님이 🌳모코숲🌳에 입장했습니다👏🏼"
            )
            await say(
                channel=event["channel"],
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": message,
                        },
                        "accessory": {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "소개 보기"},
                            "action_id": "intro_modal",
                            "value": user.user_id,
                        },
                    },
                ],
            )
        except Exception as e:
            loguru.logger.error(e)  # TODO: 디스코드 알림 보내기
            pass
