from app import models
import polars as pl


class UserRepository:
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
