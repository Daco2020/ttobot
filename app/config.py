from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    BOT_TOKEN: str = Field(env="BOT_TOKEN")
    APP_TOKEN: str = Field(env="APP_TOKEN")

    SCOPE: list = Field(env="SCOPE")
    JSON_KEYFILE_DICT: dict = Field(env="JSON_KEYFILE_DICT")
    SPREAD_SHEETS_URL: str = Field(env="SPREAD_SHEETS_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


# Constant
SUBMIT_SHEET_NAME = "raw_data"
SUBMIT_VIEW = "submit_view"
PASS_VIEW = "pass_view"
