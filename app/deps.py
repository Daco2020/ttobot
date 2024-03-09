from app.repositories import MessageRepository, UserRepository
from app.services import AppService


def app_service() -> AppService:
    message_repo = MessageRepository()
    return AppService(message_repo)


def user_repo() -> UserRepository:
    return UserRepository()
