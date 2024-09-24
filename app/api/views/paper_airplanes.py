from starlette import status
from fastapi import APIRouter, Depends, Query
from app.api.deps import api_service
from app.api.services import ApiService
from app.api import dto


router = APIRouter()


@router.get(
    "/paper_airplanes/sent",
    status_code=status.HTTP_200_OK,
    response_model=dto.PaperAirplaneResponse,
)
async def fetch_sent_paper_airplanes(
    user_id: str,
    offset: int = 0,
    limit: int = Query(default=50, le=50),
    service: ApiService = Depends(api_service),
) -> dto.PaperAirplaneResponse:
    """조건에 맞는 종이비행기를 가져옵니다."""
    count, data = service.fetch_sent_paper_airplanes(
        user_id=user_id, offset=offset, limit=limit
    )
    return dto.PaperAirplaneResponse(
        count=count, data=[each.model_dump() for each in data]
    )


@router.get(
    "/paper_airplanes/received",
    status_code=status.HTTP_200_OK,
    response_model=dto.PaperAirplaneResponse,
)
async def fetch_received_paper_airplanes(
    user_id: str,
    offset: int = 0,
    limit: int = Query(default=50, le=50),
    service: ApiService = Depends(api_service),
) -> dto.PaperAirplaneResponse:
    """조건에 맞는 종이비행기를 가져옵니다."""
    count, data = service.fetch_received_paper_airplanes(
        user_id=user_id, offset=offset, limit=limit
    )
    return dto.PaperAirplaneResponse(
        count=count, data=[each.model_dump() for each in data]
    )
