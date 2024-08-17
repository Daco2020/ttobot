from app.api.repositories import UserRepository
from app.api.services import AppService


def app_service() -> AppService:
    return AppService()


def user_repo() -> UserRepository:
    return UserRepository()
