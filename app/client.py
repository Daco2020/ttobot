from app.dto import Submission
from app.config import settings, SUBMIT_SHEET_NAME

import gspread  # type: ignore
from oauth2client.service_account import ServiceAccountCredentials  # type: ignore


credentials = ServiceAccountCredentials.from_json_keyfile_name(
    settings.JSON_FILE_NAME, settings.SCOPE
)
gc = gspread.authorize(credentials)


class SpreadSheetClient:
    def __init__(self) -> None:
        self._doc = gc.open_by_url(settings.SPREAD_SHEETS_URL)
        self._worksheet = self._doc.worksheet(SUBMIT_SHEET_NAME)

    def submit(self, submission: Submission) -> None:
        values_list = self._worksheet.get_all_values()
        self._worksheet.update(
            f"A{len(values_list) + 1}",
            [
                [
                    submission.username,
                    submission.content_url,
                    submission.dt,
                    submission.category,
                    submission.description,
                    submission.tag,
                ]
            ],
        )
