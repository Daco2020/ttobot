import csv
from fastapi import APIRouter, status

router = APIRouter()


@router.get(
    "/writing-participation",
    status_code=status.HTTP_200_OK,
)
async def fetch_writing_participation() -> list[dict[str, str]]:
    """글쓰기 참여 신청 목록을 가져옵니다."""
    with open("store/writing_participation.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        data = [each for each in reader]
    return data
