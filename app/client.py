from typing import Any
from app.logging import logger
from app.config import settings

from gspread import authorize, Spreadsheet, Worksheet
from gspread.exceptions import APIError, WorksheetNotFound
from gspread.utils import rowcol_to_a1
from oauth2client.service_account import ServiceAccountCredentials


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


def is_quota_error(error: Exception) -> bool:
    """시트 API 한도 초과(429)인지 판별한다. 429 만 틱 단위 백오프 대상이다."""
    if not isinstance(error, APIError):
        return False
    return getattr(getattr(error, "response", None), "status_code", None) == 429


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

    def batch_get(self, ranges: list[str]) -> list[list[list[str]]]:
        """여러 범위를 한 번의 읽기 요청으로 가져와 요청 순서대로 rows 리스트를 돌려준다.

        빈 시트는 응답에 values 키가 없으므로 [] 로 정규화한다.
        """
        if not ranges:
            return []
        response = self._doc.values_batch_get(ranges)
        return [vr.get("values", []) for vr in response.get("valueRanges", [])]

    def batch_update(self, data: list[dict[str, Any]]) -> None:
        """여러 시트의 여러 범위를 한 번의 쓰기 요청으로 갱신한다 (values.batchUpdate = 1건)."""
        if not data:
            return
        self._doc.values_batch_update({"valueInputOption": "RAW", "data": data})

    def replace_table(self, sheet_name: str, values: list[list[str]]) -> None:
        """시트를 values 로 통째로 바꾼다. 쓰기 1회, 원자적.

        기존 grid 행 수(row_count, 캐시 메타라 API 호출 없음)까지 빈 행으로 채워 잔여 행을
        지운다. clear + append 는 쓰기 2회에 그 사이 빈 창이 생기므로 쓰지 않는다.
        """
        if not values:
            return
        sheet = self._sheets[sheet_name]
        ncols = len(values[0])
        rows = max(len(values), int(sheet.row_count))
        padded = values + [[""] * ncols] * (rows - len(values))
        sheet.update(values=padded, range_name=f"A1:{rowcol_to_a1(rows, ncols)}")

    def _batch_append_rows(
        self,
        values: list[list[str]],
        sheet: Worksheet,
        batch_size: int,
    ) -> None:
        for i in range(0, len(values), batch_size):
            batch = values[i : i + batch_size]
            sheet.append_rows(batch)
