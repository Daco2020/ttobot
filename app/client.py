from dataclasses import asdict
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

    def submit(self, dto: dto.Submission | dto.Pass) -> None:
        data = asdict(dto)
        values = self._worksheet.get_all_values()
        self._worksheet.update(
            f"A{len(values) + 1}",
            [
                [
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
        values = self._worksheet.get_values("A2:G")
        user_data = [value for value in values if value[0] == username]
        return len([data for data in user_data if data[5] == "pass"])
