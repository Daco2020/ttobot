from app.repositories import MessageRepository
from app.services import AppService


def get_app_service() -> AppService:
    message_repo = MessageRepository()
    return AppService(message_repo)
