from typing import Any
from starlette import status
from fastapi import APIRouter, Depends, HTTPException
from app.api.auth import current_user
from app.models import SimpleUser
from app.config import settings

import csv

router = APIRouter()


@router.get(
    "/inflearn/coupons",
    status_code=status.HTTP_200_OK,
)
async def fetch_inflearn_coupons(
    user: SimpleUser = Depends(current_user),
) -> dict[str, Any]:
    """인프런 쿠폰 정보를 가져옵니다."""
    if user.user_id not in settings.ADMIN_IDS:
        raise HTTPException(status_code=403, detail="조회 권한이 없습니다.")

    with open("store/_inflearn_coupon.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        data = [each for each in reader]

    return {"data": data}
