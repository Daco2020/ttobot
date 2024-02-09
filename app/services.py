from app.repositories import MessageRepository


class AppService:
    def __init__(self, message_repo: MessageRepository) -> None:
        self._message_repo = message_repo
