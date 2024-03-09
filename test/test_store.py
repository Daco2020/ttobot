import csv
import pytest
from app.config import settings
from pydantic import ValidationError
from app.client import SpreadSheetClient
from app.models import Content, User, Bookmark
from gspread import authorize
from oauth2client.service_account import ServiceAccountCredentials


def test_valid_content_loading() -> None:
    with open("store/contents.csv") as f:
        reader = csv.DictReader(f)
        for content in reader:
            try:
                Content(**content)
            except ValidationError:
                pytest.fail("ValidationError should not occur!")


def test_valid_user_loading() -> None:
    with open("store/users.csv") as f:
        reader = csv.DictReader(f)
        for user in reader:
            try:
                User(**user)  # type: ignore
            except ValidationError:
                pytest.fail("ValidationError should not occur!")


def test_valid_bookmark_loading() -> None:
    with open("store/bookmark.csv") as f:
        reader = csv.DictReader(f)
        for user in reader:
            try:
                Bookmark(**user)  # type: ignore
            except ValidationError:
                pytest.fail("ValidationError should not occur!")


@pytest.fixture
def client() -> SpreadSheetClient:
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        settings.JSON_KEYFILE_DICT, settings.SCOPE
    )
    gc = authorize(credentials)
    doc = gc.open_by_url(settings.SPREAD_SHEETS_URL)
    client = SpreadSheetClient(doc=doc, sheets=dict(test=doc.worksheet("test")))
    client.clear("test")
    return client


# def test_content_upload_queue(client: SpreadSheetClient) -> None:
#     """대량의 콘텐츠 업로드기 동작하는지 확인합니다."""
#     # given
#     data = []
#     for i in range(0, 10, 2):
#         data.append(
#             [
#                 Content(
#                     user_id=f"test_user_id_{i}_{j}",
#                     username=f"test_username_{i}_{j}",
#                     description=f"test_description_{i}_{j}",
#                     type="submit",
#                     content_url=f"test_conten_url_{i}_{j}",
#                     title=f"test_title_{i}_{j}",
#                     category="test_category",
#                     tags="test_tags",
#                     curation_flag="Y",
#                 ).to_list_for_sheet()
#                 for j in range(1, i + 1)
#             ]
#         )

#     # when
#     for values in data:
#         for value in values:
#             store.content_upload_queue.append(value)
#             Store(client).upload_queue(contents="test")

#     # then
#     actual = client.get_values("test")
#     assert len(actual) == 20
