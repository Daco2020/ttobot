from typing import Any
from app.logging import logger
from app.config import settings

from gspread import authorize, Spreadsheet, Worksheet
from gspread.exceptions import WorksheetNotFound
from oauth2client.service_account import ServiceAccountCredentials
from app.models import StoreModel


credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    settings.JSON_KEYFILE_DICT, settings.SCOPE
)
gc = authorize(credentials)

# writing_participation 탭 헤더. store/writing_participation.csv 의 컬럼과 같아야 한다.
WRITING_PARTICIPATION_HEADER = [
    "user_id",
    "name",
    "created_at",
    "is_writing_participation",
]


def _get_or_create_worksheet(
    doc: Spreadsheet, name: str, header: list[str]
) -> Worksheet:
    """탭이 없으면 만들고 헤더를 쓴다. 있으면 그대로 돌려준다.

    새로 추가되는 탭이 아직 시트에 없는 상태로 배포돼도 부팅이 죽지 않게 한다.
    """
    try:
        return doc.worksheet(name)
    except WorksheetNotFound:
        sheet = doc.add_worksheet(title=name, rows=1000, cols=len(header))
        sheet.append_row(header)
        logger.info(f"시트 탭 생성: {name}")
        return sheet


class SpreadSheetClient:
    _instance = None

    def __new__(cls, *args, **kwargs):
        # __init__ 이 doc/sheets 를 받으므로 __new__ 도 같은 인자를 받아 넘겨야 한다.
        # (인자는 super().__new__ 에 넘기지 않는다. object.__new__ 는 인자를 받지 않음)
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        doc: Spreadsheet = gc.open_by_url(settings.SPREAD_SHEETS_URL),
        sheets: dict[str, Worksheet] | None = None,
    ) -> None:
        if not hasattr(self, "_initialized"):
            self._doc = doc
            self._sheets = (
                {
                    "contents": self._doc.worksheet("contents"),
                    "users": self._doc.worksheet("users"),
                    "logs": self._doc.worksheet("logs"),
                    "backup": self._doc.worksheet("backup"),
                    "bookmark": self._doc.worksheet("bookmark"),
                    "coffee_chat_proof": self._doc.worksheet("coffee_chat_proof"),
                    "point_histories": self._doc.worksheet("point_histories"),
                    "paper_plane": self._doc.worksheet("paper_plane"),
                    "subscriptions": self._doc.worksheet("subscriptions"),
                    "writing_participation": _get_or_create_worksheet(
                        self._doc, "writing_participation", WRITING_PARTICIPATION_HEADER
                    ),
                }
                if not sheets
                else sheets
            )
            self._initialized = True

    def get_values(self, sheet_name: str, column: str = "") -> list[list[str]]:
        """스프레드 시트로 부터 값을 가져옵니다."""
        if column:
            return self._sheets[sheet_name].get_values(column)
        else:
            return self._sheets[sheet_name].get_all_values()

    def backup(self, values: list[list[str]]) -> None:
        """백업 시트에 데이터를 업로드 합니다."""
        # TODO: 추후 백업 시트를 자동 생성할 수 있도록 변경 필요
        sheet = self._sheets["backup"]
        sheet.clear()
        self._batch_append_rows(values, sheet, batch_size=1000)

    def clear(self, sheet_name: str) -> None:
        """해당 시트의 모든 데이터를 삭제합니다."""
        self._sheets[sheet_name].clear()

    def upload(self, sheet_name: str, values: list[list[str]]) -> None:
        """해당 시트에 데이터를 하나씩 업로드 합니다."""
        sheet = self._sheets[sheet_name]
        for value in values:
            sheet.append_row(value)

    def bulk_upload(self, sheet_name: str, values: list[list[str]]) -> None:
        """해당 시트에 데이터를 업로드 합니다."""
        sheet = self._sheets[sheet_name]
        self._batch_append_rows(values, sheet, batch_size=1000)

    def update_bookmark(self, sheet_name: str, obj: StoreModel) -> None:
        """해당 객체 정보를 시트에 업데이트 합니다."""
        sheet = self._sheets[sheet_name]
        records = sheet.get_all_records()

        target_record = dict()
        row_number = 2  # 1은 인덱스가 0부터 시작하기 때문이며 나머지 1은 시드 헤더 행이 있기 때문.
        for idx, record in enumerate(records):
            # TODO: 추후 조건 바꾸기
            if obj.user_id == record["user_id"] and obj.content_ts == str(  # type: ignore
                record["content_ts"]
            ):
                target_record = record
                row_number += idx
                break

        values = obj.to_list_for_sheet()

        if not target_record:
            logger.error(f"시트에 해당 값이 존재하지 않습니다. {values}")

        sheet.update(f"A{row_number}:G{row_number}", [values])

    def update_subscription(
        self,
        sheet_name: str,
        subscription_dict: dict[str, Any],
    ) -> None:
        """해당 객체 정보를 시트에 업데이트 합니다."""
        sheet = self._sheets[sheet_name]
        records = sheet.get_all_records()

        target_record = dict()
        row_number = 2  # 1은 인덱스가 0부터 시작하기 때문이며 나머지 1은 시드 헤더 행이 있기 때문.
        for idx, record in enumerate(records):
            if subscription_dict["id"] == record["id"]:
                target_record = record
                row_number += idx
                break

        values = list(subscription_dict.values())

        if not target_record:
            logger.error(f"시트에 해당 값이 존재하지 않습니다. {values}")

        sheet.update(f"A{row_number}:G{row_number}", [values])

    def update_user(self, sheet_name: str, values: list[str]) -> None:
        """유저 정보를 시트에 업데이트 합니다."""
        # TODO: 추후 업데이트 함수 통합하기
        sheet = self._sheets[sheet_name]
        records = sheet.get_all_records()

        target_record = dict()
        row_number = 2  # 1은 인덱스가 0부터 시작하기 때문이며 나머지 1은 시드 헤더 행이 있기 때문.
        for idx, record in enumerate(records):
            if values[0] == record["user_id"]:
                target_record = record
                row_number += idx
                break

        if not target_record:
            logger.error(f"시트에 해당 값이 존재하지 않습니다. {values}")

        sheet.update(f"A{row_number}:F{row_number}", [values])

    def _batch_append_rows(
        self,
        values: list[list[str]],
        sheet: Worksheet,
        batch_size: int,
    ) -> None:
        for i in range(0, len(values), batch_size):
            batch = values[i : i + batch_size]
            sheet.append_rows(batch)
