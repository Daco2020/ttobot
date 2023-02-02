from dataclasses import asdict
from typing import Tuple
from app import dto
from app.config import PASS_DATA, RAW_DATA, USERS_DATA, settings

import gspread  # type: ignore
from oauth2client.service_account import ServiceAccountCredentials  # type: ignore


credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    settings.JSON_KEYFILE_DICT, settings.SCOPE
)
gc = gspread.authorize(credentials)


class SpreadSheetClient:
    def __init__(self) -> None:
        self._doc = gc.open_by_url(settings.SPREAD_SHEETS_URL)
        self._raw_data = self._doc.worksheet(RAW_DATA)
        self._pass_data = self._doc.worksheet(PASS_DATA)
        self._users_data = self._doc.worksheet(USERS_DATA)

    def submit(self, dto: dto.Submit) -> None:
        data = asdict(dto)
        cursor = len(self._raw_data.get_values("A:A")) + 1
        self._raw_data.update(
            f"A{cursor}",
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

    def get_remaining_pass_count(self, user_id: str) -> Tuple[int, str]:
        """스프레스시트로부터 패스 사용 수를 가져옵니다."""
        pass_data = self._pass_data.get_values("A3:D")
        pass_count = 0
        before_type = ""
        for data in pass_data:
            if data[2] == user_id:
                pass_count = int(data[3])
                before_type = data[1]
                break
        return pass_count, before_type

    def fetch_all_submit(self, username: str) -> list[dto.Submit]:
        """유저의 제출이력을 모두 가져옵니다."""
        values = self._raw_data.get_values("A2:H")
        return self._sorted_submit(values, username)

    def _sorted_submit(self, values: list[str], username: str) -> list[dto.Submit]:
        """유저의 제출이력을 최신순으로 정렬하여 반환합니다."""
        raw_data = [value for value in values if value[1] == username]
        desc_data = sorted(raw_data, key=lambda x: x[3], reverse=True)
        return [
            dto.Submit(
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
