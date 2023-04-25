import abc
import csv
from typing import Any

from app import models, client


class ContentDao(abc.ABC):
    @abc.abstractmethod
    def fetch_all(self) -> list[models.Content]:
        """모든 콘텐츠를 내림차순(날짜)으로 정렬하여 가져옵니다."""
        ...

    @abc.abstractmethod
    def fetch_by_keyword(self, keyword) -> list[models.Content]:
        """키워드를 포함하는 콘텐츠를 내림차순(날짜)으로 정렬하여 가져옵니다."""
        ...

    @abc.abstractmethod
    def get_user_id(self, name: str) -> str | None:
        """유저의 이름을 받아서 user_id를 반환합니다."""
        ...


class FileContentDao(ContentDao):
    def __init__(self) -> None:
        ...

    def fetch_all(self) -> list[models.Content]:
        with open("db/contents.csv", "r") as f:
            reader = csv.DictReader(f)
            contents = [
                models.Content(**content)
                for content in reader
                if content["type"] == "submit"
            ]
            return sorted(contents, key=lambda content: content.dt_, reverse=True)

    def fetch_by_keyword(self, keyword) -> list[models.Content]:
        with open("db/contents.csv", "r") as f:
            reader = csv.DictReader(f)
            contents = [
                models.Content(**content)
                for content in reader
                if keyword
                in content["title"] + content["description"] + content["tags"]
                and content["type"] == "submit"
            ]
            return sorted(contents, key=lambda content: content.dt_, reverse=True)

    def get_user_id(self, name: str) -> str | None:
        with open("db/users.csv", "r") as f:
            reader = csv.DictReader(f)
            for user in reader:
                if user["name"] == name:
                    return user["user_id"]
