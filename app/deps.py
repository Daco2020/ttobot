from app.repositories import UserRepository
from app.services import AppService


def app_service() -> AppService:
    return AppService()


def user_repo() -> UserRepository:
    return UserRepository()
