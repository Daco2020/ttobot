import abc
import csv
from typing import Any

from app import models, client


class UserRepository(abc.ABC):
    @abc.abstractmethod
    def get(self, user_id: str) -> models.User | None:
        ...

    @abc.abstractmethod
    def fetch(self) -> list[models.User]:
        ...

    @abc.abstractmethod
    def update(self, content) -> None:
        ...


class FileUserRepository(UserRepository):
    def __init__(self) -> None:
        ...

    def get(self, user_id: str) -> models.User | None:
        """유저와 콘텐츠를 가져옵니다."""
        if user := self._get_user(user_id):
            user.contents = self._fetch_contents(user_id)
            return user
        return None

    def fetch(self) -> list[models.User]:
        """모든 유저와 콘텐츠를 가져옵니다."""
        users = self._fetch_users()
        for user in users:
            user["contents"] = self._fetch_contents(user["user_id"])
        return [models.User(**user) for user in users]

    def update(self, user: models.User) -> None:
        """유저의 콘텐츠를 업데이트합니다."""
        if not user.contents:
            raise ValueError("업데이트 대상 content 가 없습니다.")
        line = user.recent_content.to_line_for_csv()
        client.upload_queue.append(user.recent_content.to_list_for_sheet())
        with open("store/contents.csv", "a") as f:
            f.write(line + "\n")

    def _get_user(self, user_id: str) -> models.User | None:
        """유저를 가져옵니다."""
        users = self._fetch_users()
        for user in users:
            if user["user_id"] == user_id:
                return models.User(**user)
        return None

    def _fetch_users(self) -> list[dict[str, Any]]:
        """모든 유저를 가져옵니다."""
        with open("store/users.csv", "r") as f:
            reader = csv.DictReader(f)
            users = [dict(row) for row in reader]
            return users

    def _fetch_contents(self, user_id: str) -> list[models.Content]:
        """유저의 콘텐츠를 오름차순(날짜)으로 정렬하여 가져옵니다."""
        with open("store/contents.csv", "r") as f:
            reader = csv.DictReader(f)
            contents = [
                models.Content(**content)
                for content in reader
                if content["user_id"] == user_id
            ]
            return sorted(contents, key=lambda content: content.dt_)
