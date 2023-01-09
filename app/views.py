from fastapi import Depends
from fastapi.routing import APIRouter
from starlette.status import HTTP_201_CREATED
from app.deps import submit_service
from app.services import SubmitService

router = APIRouter()


@router.post(
    "/test",
    status_code=HTTP_201_CREATED,
)
async def submit(submit_service: SubmitService = Depends(submit_service)) -> None:
    await submit_service.submit()
