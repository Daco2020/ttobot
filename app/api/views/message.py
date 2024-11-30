from typing import Any
from starlette import status
from fastapi import APIRouter, Depends, HTTPException
from app.api.auth import current_user
from app.api.dto import SendMessageDTO
from app.models import SimpleUser
from app.config import settings
from app.slack.event_handler import app as slack_app


router = APIRouter()


@router.post(
    "/send-messages",
    status_code=status.HTTP_200_OK,
)
async def send_messages(
    dto_list: list[SendMessageDTO],
    user: SimpleUser = Depends(current_user),
) -> dict[str, Any]:
    """메시지를 보냅니다."""
    if user.user_id not in settings.ADMIN_IDS:
        raise HTTPException(status_code=403, detail="메시지 전송 권한이 없습니다.")

    for dto in dto_list:
        await slack_app.client.chat_postMessage(
            channel=dto.channel_id,
            text=dto.message,
        )

    return {"message": "메시지를 보냈습니다."}
