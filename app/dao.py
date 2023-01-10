import abc
import datetime

from app import clients


class SpreadSheetsDao:
    def __init__(self, client: clients.SpreadSheetsClient) -> None:
        self._client = client

    async def submit(
        self,
        username: str,
        content_url: str,
        dt: datetime.datetime,
        category: str,
        tag: str,
    ) -> None:
        print(username, content_url, dt, category, tag)
        print("제출")


sheets_Dao = SpreadSheetsDao(clients.SpreadSheetsClient())
