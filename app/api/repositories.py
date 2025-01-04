import csv
from app import models
import polars as pl


class ApiRepository:
    def __init__(self) -> None: ...

    def get_user(self, user_id: str) -> models.User | None:
        """특정 유저를 조회합니다."""
        df = pl.read_csv(
            "store/users.csv", dtypes={"deposit": pl.Utf8}
        )  # pl은 deposit 을 int로 인식하기 때문에 str로 변경
        users = df.filter(pl.col("user_id") == user_id).to_dicts()

        return models.User(**users[0]) if users else None

    def fetch_users(self) -> list[models.User]:
        """모든 유저를 조회합니다."""
        df = pl.read_csv("store/users.csv", dtypes={"deposit": pl.Utf8})
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

    def fetch_paper_planes(self, sender_id: str) -> list[models.PaperPlane]:
        """종이비행기를 가져옵니다."""
        with open("store/paper_plane.csv") as f:
            reader = csv.DictReader(f)
            paper_planes = [
                models.PaperPlane(**paper_plane)  # type: ignore
                for paper_plane in reader
                if paper_plane["sender_id"] == sender_id
            ]
            return paper_planes

    def create_paper_plane(self, paper_plane: models.PaperPlane) -> None:
        """종이비행기를 생성합니다."""
        with open("store/paper_plane.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(paper_plane.to_list_for_csv())
