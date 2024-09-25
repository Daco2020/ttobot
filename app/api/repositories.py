from app import models
import polars as pl


class ApiRepository:
    def __init__(self) -> None: ...

    def get_user(self, user_id: str) -> models.User | None:
        """특정 유저를 조회합니다."""
        df = pl.read_csv("store/users.csv")
        user = df.filter(pl.col("user_id") == user_id).to_dict()
        return models.User(**user) if user else None

    def fetch_users(self) -> list[models.User]:
        """모든 유저를 조회합니다."""
        df = pl.read_csv("store/users.csv")
        return [models.User(**row) for row in df.to_dicts()]

    def fetch_sent_paper_planes(
        self,
        sender_id: str,
        offset: int,
        limit: int,
    ) -> tuple[int, list[models.PaperPlane]]:
        """유저가 보낸 종이비행기를 가져옵니다."""
        df = pl.read_csv("store/paper_plane.csv")
        data = df.filter(pl.col("sender_id") == sender_id).sort(
            "created_at", descending=True
        )
        count = len(data)
        paper_planes = data.slice(offset, limit).to_dicts()
        return count, [models.PaperPlane(**paper_plane) for paper_plane in paper_planes]

    def fetch_received_paper_planes(
        self,
        receiver_id: str,
        offset: int,
        limit: int,
    ) -> tuple[int, list[models.PaperPlane]]:
        """유저가 받은 종이비행기를 가져옵니다."""
        df = pl.read_csv("store/paper_plane.csv")
        data = df.filter(pl.col("receiver_id") == receiver_id).sort(
            "created_at", descending=True
        )
        count = len(data)
        paper_planes = data.slice(offset, limit).to_dicts()
        return count, [models.PaperPlane(**paper_plane) for paper_plane in paper_planes]
