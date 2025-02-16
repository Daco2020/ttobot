import asyncio
from enum import StrEnum
from typing import Any

from starlette import status
from fastapi import APIRouter, Depends, HTTPException
from app.api.auth import current_user
from app.api.deps import point_service
from app.models import SimpleUser
from app.slack.services.point import PointService
from app.slack_notification import send_point_noti_message
from app.config import settings
from app.slack.event_handler import app as slack_app


class PointTypeEnum(StrEnum):
    CURATION = "curation"
    VILLAGE_CONFERENCE = "village_conference"
    SPECIAL = "special"


router = APIRouter()


@router.post(
    "/points",
    status_code=status.HTTP_200_OK,
)
async def grant_points(
    user_ids: list[str],
    point_type: PointTypeEnum,
    text: str = "",
    point: int = 0,
    reason: str = "",
    user: SimpleUser = Depends(current_user),
    point_service: PointService = Depends(point_service),
) -> dict[str, Any]:
    """
    관리자가 여러 유저에게 포인트를 지급하는 API입니다.
    """
    if user.user_id not in settings.ADMIN_IDS:
        raise HTTPException(status_code=403, detail="지급 권한이 없습니다.")

    if point_type == PointTypeEnum.CURATION:
        for user_id in user_ids:
            message = point_service.grant_if_curation_selected(user_id)
            await send_point_noti_message(
                client=slack_app.client,
                channel=user_id,
                text=text + "\n" + message,
            )
            await asyncio.sleep(1)
        return {"message": "큐레이션 선정 포인트를 지급했습니다."}

    elif point_type == PointTypeEnum.VILLAGE_CONFERENCE:
        for user_id in user_ids:
            message = point_service.grant_if_village_conference_participated(user_id)
            await send_point_noti_message(
                client=slack_app.client,
                channel=user_id,
                text=text + "\n" + message,
            )
            await asyncio.sleep(1)
        return {"message": "빌리지 반상회 참여 포인트를 지급했습니다."}

    elif point_type == PointTypeEnum.SPECIAL:
        if not point or not reason:
            raise HTTPException(
                status_code=400,
                detail="특별 보너스 포인트는 point와 reason이 필요합니다.",
            )
        for user_id in user_ids:
            message = point_service.grant_if_special_point(user_id, point, reason)
            await send_point_noti_message(
                client=slack_app.client,
                channel=user_id,
                text=text + "\n" + message,
            )
            await asyncio.sleep(1)
        return {"message": "특별 포인트를 지급했습니다."}
