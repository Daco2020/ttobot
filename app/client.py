from dataclasses import asdict
from datetime import datetime, timedelta
from app import dto
from app.config import settings, SUBMIT_SHEET_NAME

import gspread  # type: ignore
from oauth2client.service_account import ServiceAccountCredentials  # type: ignore


credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    settings.JSON_KEYFILE_DICT, settings.SCOPE
)
gc = gspread.authorize(credentials)


class SpreadSheetClient:
    def __init__(self) -> None:
        self._doc = gc.open_by_url(settings.SPREAD_SHEETS_URL)
        self._worksheet = self._doc.worksheet(SUBMIT_SHEET_NAME)

    def submit(self, dto: dto.Submit) -> None:
        data = asdict(dto)
        values = self._worksheet.get_all_values()
        self._worksheet.update(
            f"A{len(values) + 1}",
            [
                [
                    data.get("user_id"),
                    data.get("username"),
                    data.get("content_url"),
                    data.get("dt"),
                    data.get("category"),
                    data.get("description"),
                    data.get("type"),
                    data.get("tag"),
                ]
            ],
        )

    def get_passed_count(self, username: str) -> int:
        """스프레스시트로부터 패스 사용 수를 가져옵니다."""
        # TODO: 스프레드 시트에서 사용가능 패스 수를 직접 가져오도록 수정필요
        user_data = self.fetch_all_submit(username)
        return len([data for data in user_data if data.get("type") == "pass"])

    def is_passable(self, username: str) -> bool:
        """패스가 가능한지 불린 타입으로 반환합니다."""
        user_data = self.fetch_all_submit(username)
        if not user_data:
            return True
        # TODO: 스프레드시트 호출 변경

        # recent_data = user_data[0]
        # if recent_data.get("type") != "pass":
        #     return True
        # if self._date(recent_data) < datetime.now().date() - timedelta(days=27):
        #     return True
        return False

    def fetch_all_submit(self, username: str) -> list[dict[str, str]]:
        """유저의 제출이력을 모두 가져옵니다."""
        values = self._worksheet.get_values("A2:H")
        return self._to_dict(values, username)

    def _to_dict(self, values: list[str], username: str) -> list[dict[str, str]]:
        """유저의 제출이력을 최신순으로 정렬하여 반환합니다."""
        raw_data = [value for value in values if value[1] == username]
        desc_data = sorted(raw_data, key=lambda x: x[3], reverse=True)
        return [
            dict(
                user_id=data[0],
                username=data[1],
                content_url=data[2],
                dt=data[3],
                category=data[4],
                description=data[5],
                type=data[6],
                tag=data[7],
            )
            for data in desc_data
        ]

    # def _date(self, data: dict[str, str]) -> datetime:
    #     dt = datetime.strptime(data.get("dt"), "%Y-%m-%d %H:%M:%S")
    #     return dt.date()
