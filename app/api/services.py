from app import models
from app.api.repositories import ApiRepository


class ApiService:
    def __init__(self, api_repo: ApiRepository) -> None:
        self._repo = api_repo

    def fetch_sent_paper_airplanes(
        self,
        user_id: str,
        offset: int,
        limit: int,
    ) -> tuple[int, list[models.PaperAirplane]]:
        """유저가 보낸 종이비행기를 가져옵니다."""
        return self._repo.fetch_sent_paper_airplanes(
            sender_id=user_id,
            offset=offset,
            limit=limit,
        )

    def fetch_received_paper_airplanes(
        self,
        user_id: str,
        offset: int,
        limit: int,
    ) -> tuple[int, list[models.PaperAirplane]]:
        """유저가 받은 종이비행기를 가져옵니다."""
        return self._repo.fetch_received_paper_airplanes(
            receiver_id=user_id, offset=offset, limit=limit
        )
