from fastapi import Depends
from app.clients import SpreadSheetsClient
from app.dao import SpreadSheetsSubmitDao, SubmitDao
from app.services import SubmitService


def submit_dao() -> SubmitDao:
    client = SpreadSheetsClient()
    return SpreadSheetsSubmitDao(client)


def submit_service(submit_dao: SubmitDao = Depends(submit_dao)) -> SubmitService:
    return SubmitService(submit_dao)
