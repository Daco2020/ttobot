import abc

from app import models


class UserRepository(abc.ABC):
    @abc.abstractmethod
    def get(self, user_id: str) -> models.User | None:
        ...

    @abc.abstractmethod
    def update(self, content) -> None:
        ...


class FileUserRepository(UserRepository):
    def __init__(self) -> None:
        ...

    def update(self, user: models.User) -> None:
        if not user.contents:
            raise ValueError("업데이트 대상 content 가 없습니다.")
        content = user.contents.pop()
        with open("store/contents.csv", "a") as f:
            # TODO: 형식 맞춰서 저장하기
            f.write(f"{content}\n")

    def get(self, user_id: str) -> models.User | None:
        user = self._get_user(user_id)
        if not user:
            return None
        contents = self._fetch_contents(user_id)
        user.contents = contents
        return user

    def _get_user(self, user_id: str) -> models.User | None:
        with open("store/users.csv", "r") as f:
            lines = f.read().splitlines()
            columns = lines[0].split(",")
            users = self._to_dict(columns, lines)
            for user in users:
                if user["user_id"] == user_id:
                    return models.User(**user)
            return None

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

    def _to_dict(self, columns: list[str], lines: list[str]) -> list[dict[str, str]]:
        return [dict(zip(columns, line.split(","))) for line in lines[1:]]
