from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.auth import current_user
from app.api.deps import api_service
from app.api.services import ApiService
from app.api import dto
from app.constants import BOT_IDS
from app.models import SimpleUser
from app.config import settings
from app.slack.event_handler import app as slack_app

router = APIRouter()


class SendPaperPlaneCreateIn(BaseModel):
    receiver_id: str
    text: str


@router.post(
    "/paper-planes",
    status_code=status.HTTP_201_CREATED,
)
async def send_paper_plane(
    dto: SendPaperPlaneCreateIn,
    service: ApiService = Depends(api_service),
    user: SimpleUser = Depends(current_user),
) -> dict[str, str]:
    """종이비행기를 보냅니다."""
    if user.user_id == dto.receiver_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="종이비행기는 자신에게 보낼 수 없어요. 😉",
        )

    if len(dto.text) > 300:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="종이비행기 메시지는 300자 이내로 작성해주세요. 😉",
        )

    if dto.receiver_id in BOT_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="봇에게 종이비행기를 보낼 수 없어요. 😉",
        )

    if user.user_id == settings.SUPER_ADMIN:
        pass
    else:
        paper_planes = service.fetch_current_week_paper_planes(user_id=user.user_id)
        if len(paper_planes) >= 7:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="종이비행기는 한 주에 7개까지 보낼 수 있어요. (토요일 00시에 충전)",
            )

    await service.send_paper_plane(
        sender_id=user.user_id,
        sender_name=user.name,
        receiver_id=dto.receiver_id,
        text=dto.text,
        client=slack_app.client,
    )
    return {"message": "종이비행기를 보냈습니다."}


@router.get(
    "/paper-planes/sent",
    status_code=status.HTTP_200_OK,
    response_model=dto.PaperPlaneResponse,
)
async def fetch_sent_paper_planes(
    offset: int = 0,
    limit: int = Query(default=1000, le=1000),  # TODO: 무한 스크롤 구현 시 수정
    service: ApiService = Depends(api_service),
    user: SimpleUser = Depends(current_user),
) -> dto.PaperPlaneResponse:
    """조건에 맞는 종이비행기를 가져옵니다."""
    count, data = service.fetch_sent_paper_planes(
        user_id=user.user_id, offset=offset, limit=limit
    )
    return dto.PaperPlaneResponse(
        count=count, data=[each.model_dump() for each in data]
    )


@router.get(
    "/paper-planes/received",
    status_code=status.HTTP_200_OK,
    response_model=dto.PaperPlaneResponse,
)
async def fetch_received_paper_planes(
    offset: int = 0,
    limit: int = Query(default=1000, le=1000),  # TODO: 무한 스크롤 구현 시 수정
    service: ApiService = Depends(api_service),
    user: SimpleUser = Depends(current_user),
) -> dto.PaperPlaneResponse:
    """조건에 맞는 종이비행기를 가져옵니다."""
    count, data = service.fetch_received_paper_planes(
        user_id=user.user_id, offset=offset, limit=limit
    )
    return dto.PaperPlaneResponse(
        count=count, data=[each.model_dump() for each in data]
    )
