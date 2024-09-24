from fastapi import Depends
from app.api.repositories import ApiRepository
from app.api.services import ApiService


def api_repo() -> ApiRepository:
    return ApiRepository()


def api_service(api_repo: ApiRepository = Depends(api_repo)) -> ApiService:
    return ApiService(api_repo=api_repo)
