from app.config import RAW_DATA_SHEET, TEST_SHEET, USERS_SHEET, settings

import gspread  # type: ignore
from oauth2client.service_account import ServiceAccountCredentials  # type: ignore

from app.utils import now_dt


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
        self._test_sheet = self._doc.worksheet(TEST_SHEET)  # TODO 테스트용 시트

    def upload(self) -> None:
        """새로 추가된 queue 가 있다면 upload 합니다."""
        global upload_queue
        if upload_queue:
            cursor = len(self._raw_data_sheet.get_values("A:A")) + 1
            self._raw_data_sheet.update(
                f"A{cursor}",
                [line.split(",") for line in upload_queue],
            )
            print(f"{now_dt()} : Uploaded {upload_queue}")
            upload_queue = []

    def create_users(self) -> None:
        """유저 정보를 스토어에 생성합니다."""
        users = self._users_sheet.get_values("A:D")
        with open("store/users.csv", "w") as f:
            f.writelines([f"{','.join(user)}\n" for user in users])

    def create_contents(self) -> None:
        """콘텐츠 정보를 스토어에 생성합니다."""
        contents = self._raw_data_sheet.get_values("A:H")
        with open("store/contents.csv", "w") as f:
            f.writelines([f"{content}" for content in self._parse(contents)])

    def _parse(self, contents: list[list[str]]) -> list[str]:
        result = []
        for content in contents:
            content[5] = content[5].replace(",", "")
            content[7] = content[7].replace(",", "#")
            result.append(",".join(content).replace("\n", " ") + "\n")
        return result
