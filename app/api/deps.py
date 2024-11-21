from fastapi import Depends
from app.api.repositories import ApiRepository
from app.api.services import ApiService
from app.slack.repositories import SlackRepository
from app.slack.services.point import PointService


def api_repo() -> ApiRepository:
    return ApiRepository()


def api_service(api_repo: ApiRepository = Depends(api_repo)) -> ApiService:
    return ApiService(api_repo=api_repo)


def point_service() -> PointService:
    return PointService(SlackRepository())
