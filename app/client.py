from app.logging import logger
from app.config import settings

from gspread import authorize
from oauth2client.service_account import ServiceAccountCredentials
from app.models import StoreModel


credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    settings.JSON_KEYFILE_DICT, settings.SCOPE
)
gc = authorize(credentials)


class SpreadSheetClient:
    def __init__(self) -> None:
        self._doc = gc.open_by_url(settings.SPREAD_SHEETS_URL)
        self._sheets = {
            "raw_data": self._doc.worksheet("raw_data"),
            "users": self._doc.worksheet("users"),
            "logs": self._doc.worksheet("logs"),
            "backup": self._doc.worksheet("backup"),
            "bookmark": self._doc.worksheet("bookmark"),
        }

    def get_values(self, sheet_name: str, column: str = "") -> list[list[str]]:
        """스프레드 시트로 부터 값을 가져옵니다."""
        if column:
            return self._sheets[sheet_name].get_values(column)
        else:
            return self._sheets[sheet_name].get_all_values()

    def backup(self, table_name: str, values: list[list[str]]) -> None:
        """백업 시트에 데이터를 업로드 합니다."""
        # TODO: 추후 백업 시트를 자동 생성할 수 있도록 변경 필요
        sheet = self._sheets[table_name]
        sheet.clear()
        sheet.append_rows(values)

    def upload(self, sheet_name: str, values: list[list[str]]) -> None:
        sheet = self._sheets[sheet_name]
        sheet.append_rows(values)

    def update(self, sheet_name: str, obj: StoreModel) -> None:
        """해당 객체 정보를 시트에 업데이트 합니다."""
        sheet = self._sheets[sheet_name]
        records = sheet.get_all_records()

        target_record = dict()
        row_number = 2  # +1은 enumerate이 0부터 시작하기 때문, +1은 헤더 행 때문
        for idx, record in enumerate(records):
            if (  # TODO: 추후 pk 를 추가하여 조건 바꾸기
                obj.user_id == record["user_id"]  # type: ignore
                and obj.content_id == record["content_id"]  # type: ignore
            ):
                target_record = record
                row_number += idx
                break

        values = obj.to_list_for_sheet()

        if not target_record:
            logger.error(f"시트에 해당 값이 존재하지 않습니다. {values}")

        sheet.update(f"A{row_number}:F{row_number}", [values])
