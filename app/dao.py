import abc
import csv

from app import models


class ContentDao(abc.ABC):
    @abc.abstractmethod
    def fetch_all(self) -> list[models.Content]:
        """모든 콘텐츠를 내림차순(날짜)으로 정렬하여 가져옵니다."""
        ...

    @abc.abstractmethod
    def fetch_by_keyword(self, keyword: str) -> list[models.Content]:
        """키워드를 포함하는 콘텐츠를 내림차순(날짜)으로 정렬하여 가져옵니다."""
        ...

    @abc.abstractmethod
    def get_user_id_by_name(self, name: str) -> str | None:
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

    def fetch_by_keyword(self, keyword: str) -> list[models.Content]:
        with open("db/contents.csv", "r") as f:
            reader = csv.DictReader(f)
            contents = [
                models.Content(**content)
                for content in reader
                if keyword.lower()
                in (content["title"] + content["description"] + content["tags"]).lower()
                and content["type"] == "submit"
            ]
            return sorted(contents, key=lambda content: content.dt_, reverse=True)

    def get_user_id_by_name(self, name: str) -> str | None:
        with open("db/users.csv", "r") as f:
            reader = csv.DictReader(f)
            matching_users = [user for user in reader if name in user["name"]]

        if len(matching_users) == 1:  # 이름 부분 일치가 하나인 경우에만 반환
            return matching_users[0]["user_id"]
        elif len(matching_users) > 1:
            for user in matching_users:
                if user["name"] == name:
                    return user["user_id"]
        return None
