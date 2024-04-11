import csv
import pytest
from pydantic import ValidationError
from app.models import Content, User, Bookmark


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
