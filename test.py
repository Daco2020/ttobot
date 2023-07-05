import csv

from app.models import Content, User


def test_content_loading(user_id: str | None = None) -> None:
    with open("db/contents.csv", "r") as f:
        reader = csv.DictReader(f)
        try:
            if not user_id:
                for content in reader:
                    Content(**content)
            else:
                for content in reader:
                    if content["user_id"] == user_id:
                        Content(**content)
        except Exception as message:
            print(
                f"------ error ------\ntarget={user_id}\n{content=}\n{message=}\n-------------------"
            )


def test_user_loading(user_id: str | None = None) -> None:
    with open("db/users.csv", "r") as f:
        reader = csv.DictReader(f)
        try:
            if not user_id:
                for user in reader:
                    User(**user)
            else:
                for user in reader:
                    if user["user_id"] == user_id:
                        User(**user)
        except Exception as message:
            print(
                f"------ error ------\ntarget={user_id}\n{user=}\n{message=}\n-------------------"
            )


target_user_id = None

if __name__ == "__main__":
    # TODO: 추후 click 라이브러리를 사용하여 테스트할 유저를 선택할 수 있도록 개선
    test_content_loading(user_id=target_user_id)
    test_user_loading(user_id=target_user_id)
    print(f"target={target_user_id} test done!")
