import abc

from app import models, client


class UserRepository(abc.ABC):
    @abc.abstractmethod
    def update(self, content) -> None:
        ...

    @abc.abstractmethod
    def get(self, user_id: str) -> models.User | None:
        ...


class FileUserRepository(UserRepository):
    def __init__(self) -> None:
        ...

    def update(self, user: models.User) -> None:
        """유저의 콘텐츠를 업데이트합니다."""
        if not user.contents:
            raise ValueError("업데이트 대상 content 가 없습니다.")
        line = user.recent_content.to_line()
        client.upload_queue.append(line)
        with open("store/contents.csv", "a") as f:
            f.write(line + "\n")

    def get(self, user_id: str) -> models.User | None:
        """유저와 콘텐츠를 가져옵니다."""
        if user := self._get_user(user_id):
            user.contents = self._fetch_contents(user_id)
            return user
        return None

    def _get_user(self, user_id: str) -> models.User | None:
        """유저를 가져옵니다."""
        with open("store/users.csv", "r") as f:
            lines = f.read().splitlines()
            columns = lines[0].split(",")
            users = self._to_dict(columns, lines)
            for user in users:
                if user["user_id"] == user_id:
                    return models.User(**user)
            return None

    def _fetch_contents(self, user_id: str) -> list[models.Content]:
        """유저의 콘텐츠를 오름차순(날짜)으로 정렬하여 가져옵니다."""
        with open("store/contents.csv", "r") as f:
            lines = f.read().splitlines()
            columns = lines[0].split(",")
            contents = self._to_dict(columns, lines)
            return sorted(
                [
                    models.Content(**content)
                    for content in contents
                    if content["user_id"] == user_id
                ],
                key=lambda content: content.dt_,
            )

    def _to_dict(self, columns: list[str], lines: list[str]) -> list[dict[str, str]]:
        return [dict(zip(columns, line.split(","))) for line in lines[1:]]
