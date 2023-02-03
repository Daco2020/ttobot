import abc
import time

from app import models


class UserRepository(abc.ABC):
    @abc.abstractmethod
    def get(self) -> models.User:
        ...


class FileUserRepository(UserRepository):
    def __init__(self) -> None:
        ...

    def get(self, user_id: str) -> models.User:
        user = self._get_user(user_id)
        contents = self._fetch_contents(user_id)
        user.contents = contents
        return user

    def _get_user(self, user_id: str) -> models.User:
        with open("store/users.csv", "r") as f:
            lines = f.read().splitlines()
            columns = lines[0].split(",")
            users = self._to_dict(columns, lines)
            for user in users:
                if user["user_id"] == user_id:
                    return models.User(**user)
            raise ValueError(f"user_id {user_id} not found")

    def _fetch_contents(self, user_id: str) -> list[models.Content]:
        with open("store/contents.csv", "r") as f:
            lines = f.read().splitlines()
            columns = lines[0].split(",")
            contents = self._to_dict(columns, lines)
            return [
                models.Content(**content)
                for content in contents
                if content["user_id"] == user_id
            ]

    def _to_dict(
        self, columns: list[str], lines: list[list[str]]
    ) -> list[dict[str, str]]:
        return [dict(zip(columns, line.split(","))) for line in lines[1:]]


if __name__ == "__main__":
    start = time.time()
    repo = FileUserRepository()
    user = repo.get("")
    print(user)
    end = time.time()
    print(end - start)
