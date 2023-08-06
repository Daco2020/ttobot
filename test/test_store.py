import csv
import pytest

from pydantic import ValidationError
from app.models import Content, User


def test_content_loading() -> None:
    with open("store/contents.csv", "r") as f:
        reader = csv.DictReader(f)
        for content in reader:
            try:
                Content(**content)
            except ValidationError:
                pytest.fail("ValidationError should not occur!")


def test_user_loading() -> None:
    with open("store/users.csv", "r") as f:
        reader = csv.DictReader(f)
        for user in reader:
            try:
                User(**user)  # type: ignore
            except ValidationError:
                pytest.fail("ValidationError should not occur!")
