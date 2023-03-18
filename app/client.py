import csv
from app.config import RAW_DATA_SHEET, LOG_SHEET, USERS_SHEET, settings

import gspread  # type: ignore
from oauth2client.service_account import ServiceAccountCredentials  # type: ignore

from app.utils import now_dt, print_log


credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    settings.JSON_KEYFILE_DICT, settings.SCOPE
)
gc = gspread.authorize(credentials)
upload_queue: list[str] = []


class SpreadSheetClient:
    def __init__(self) -> None:
        self._doc = gc.open_by_url(settings.SPREAD_SHEETS_URL)
        self._raw_data_sheet = self._doc.worksheet(RAW_DATA_SHEET)
        self._users_sheet = self._doc.worksheet(USERS_SHEET)
        self._log_sheet = self._doc.worksheet(LOG_SHEET)

    def upload(self) -> None:
        """새로 추가된 queue 가 있다면 upload 합니다."""
        global upload_queue
        if upload_queue:
            try:
                cursor = len(self._raw_data_sheet.get_values("A:A")) + 1
                self._raw_data_sheet.update(
                    f"A{cursor}",
                    [line.split(",") for line in upload_queue],
                )
            except Exception as e:
                print_log(f"Failed {upload_queue} : {e}")
                return None
            print_log(f"Uploaded {upload_queue}")
            upload_queue = []

    def sync_users(self) -> None:
        """유저 정보를 동기화합니다."""
        users = self._users_sheet.get_values("A:D")
        with open("db/users.csv", "w") as f:
            f.writelines([f"{','.join(user)}\n" for user in users])

    def sync_contents(self) -> None:
        """콘텐츠 정보를 동기화합니다."""
        contents = self._raw_data_sheet.get_values("A:H")
        with open("db/contents.csv", "w") as f:
            f.writelines([f"{content}" for content in self._parse(contents)])

    def _parse(self, contents: list[list[str]]) -> list[str]:
        result = []
        for content in contents:
            content[5] = content[5].replace(",", "")
            content[7] = content[7].replace(",", "#")
            result.append(",".join(content).replace("\n", " ") + "\n")
        return result

    def create_logs(self) -> None:
        """로그 파일을 생성합니다."""
        with open("db/logs.csv", "w") as f:
            f.writelines(f"{now_dt()} - - 새로운 로그 파일 생성\n")

    def upload_logs(self) -> None:
        """로그 파일을 업로드합니다."""
        with open("db/logs.csv", "r") as f:
            reader = csv.reader(f)
            logs = list(reader)
        cursor = len(self._log_sheet.get_values("A:A")) + 1
        self._log_sheet.update(f"A{cursor}", logs)
