from app.dao import SubmitDao


class SubmitService:
    def __init__(self, submit_dao: SubmitDao) -> None:
        self._submit_dao = submit_dao

    async def submit(self):
        await self._submit_dao.submit(1, 2, 3, 4, 5)
