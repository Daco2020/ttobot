from pydantic import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    APP_TOKEN: str

    SCOPE: list
    JSON_KEYFILE_DICT: dict
    SPREAD_SHEETS_URL: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


# sheet constants
RAW_SHEET = "raw_data"
PASS_SHEET = "PASS_DATA"  # TODO: remove this
USERS_SHEET = "users"
TEST_SHEET = "test"

# views constants
SUBMIT_VIEW = "submit_view"
PASS_VIEW = "pass_view"
