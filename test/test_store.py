import csv

from app.models import Content, User


def test_content_loading() -> None:
    with open("store/contents.csv", "r") as f:
        reader = csv.DictReader(f)
        try:
            for content in reader:
                user_id = content["user_id"]
                Content(**content)
        except Exception as message:
            print(
                f"\033[31m------ error ------\n{user_id=}\n{content=}\n{message=}\n-------------------\033[0m"
            )


def test_user_loading() -> None:
    with open("store/users.csv", "r") as f:
        reader = csv.DictReader(f)
        try:
            for user in reader:
                user_id = user["user_id"]
                User(**user)
        except Exception as message:
            print(
                f"\033[31m------ error ------\n{user_id=}\n{user=}\n{message=}\n-------------------\033[0m"
            )


if __name__ == "__main__":
    test_content_loading()
    test_user_loading()
    print("test done.")
