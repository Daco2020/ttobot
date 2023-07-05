import csv
from app.config import BACKUP_SHEET, RAW_DATA_SHEET, LOG_SHEET, USERS_SHEET, settings

import gspread  # type: ignore
from oauth2client.service_account import ServiceAccountCredentials  # type: ignore

from app.utils import now_dt, print_log


credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    settings.JSON_KEYFILE_DICT, settings.SCOPE
)
gc = gspread.authorize(credentials)
upload_queue: list[list[str]] = []


class SpreadSheetClient:
    def __init__(self) -> None:
        self._doc = gc.open_by_url(settings.SPREAD_SHEETS_URL)
        self._raw_data_sheet = self._doc.worksheet(RAW_DATA_SHEET)
        self._users_sheet = self._doc.worksheet(USERS_SHEET)
        self._log_sheet = self._doc.worksheet(LOG_SHEET)
        self._backup_sheet = self._doc.worksheet(BACKUP_SHEET)

    def upload(self) -> None:
        """새로 추가된 queue 가 있다면 upload 합니다."""
        global upload_queue
        if upload_queue:
            try:
                cursor = len(self._raw_data_sheet.get_values("A:A")) + 1
                self._raw_data_sheet.update(f"A{cursor}", upload_queue)
            except Exception as e:
                print_log(f"Failed {upload_queue} : {e}")
                return None
            print_log(f"Uploaded {upload_queue}")
            upload_queue = []

    def fetch_users(self) -> None:
        """유저 정보를 가져옵니다."""
        users = self._users_sheet.get_values("A:E")
        with open("db/users.csv", "w") as f:
            f.writelines([f"{','.join(user)}\n" for user in users])

    def fetch_contents(self) -> None:
        """콘텐츠 정보를 가져옵니다."""
        contents = self._raw_data_sheet.get_values("A:I")
        with open("db/contents.csv", "w") as f:
            f.writelines([f"{content}" for content in self._parse(contents)])

    def push_backup(self) -> None:
        """백업 시트에 contents.csv를 업로드합니다."""
        with open("db/contents.csv", "r") as f:
            reader = csv.reader(f)
            contents = list(reader)
        self._backup_sheet.clear()  # 기존 데이터를 지웁니다.
        self._backup_sheet.append_rows(contents)  # 새로운 데이터를 추가합니다.

    def _parse(self, contents: list[list[str]]) -> list[str]:
        """
        가져온 콘텐츠를 csv 포멧에 맞게 가공합니다.
        content[0]: user_id
        content[1]: username
        content[2]: title
        content[3]: content_url
        content[4]: dt
        content[5]: categor
        content[6]: description
        content[7]: type
        content[8]: tags
        """
        result = [",".join(contents[0]) + "\n"]
        for content in contents[1:]:
            content[2] = f'"{content[2]}"'
            content[3] = f'"{content[3]}"'
            content[6] = content[6].replace(",", "")
            content[8] = content[8].replace(",", "#")
            result.append(",".join(content).replace("\n", " ") + "\n")
        return result

    def create_log_file(self) -> None:
        """로그 파일을 생성합니다."""
        with open("db/logs.csv", "w") as f:
            f.writelines(f"{now_dt()} - - 새로운 로깅을 시작합니다.\n")

    def upload_logs(self) -> None:
        """로그 파일을 업로드합니다."""
        with open("db/logs.csv", "r") as f:
            reader = csv.reader(f)
            logs = list(reader)
        cursor = len(self._log_sheet.get_values("A:A")) + 1
        self._log_sheet.update(f"A{cursor}", logs)
