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
RAW_DATA_SHEET = "raw_data"
USERS_SHEET = "users"
LOG_SHEET = "log"

# views constants
SUBMIT_VIEW = "submit_view"
PASS_VIEW = "pass_view"

# constants
URL_REGEX = r"((http|https):\/\/)?[a-zA-Z0-9.-]+(\.[a-zA-Z]{2,})"
MAX_PASS_COUNT = 2
