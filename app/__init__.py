import os
from app.client import SpreadSheetClient
from app.config import settings
from fastapi import FastAPI, Request
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from app.views import slack


api = FastAPI()


@api.post("/")
async def health(request: Request) -> bool:
    return True


@api.on_event("startup")
async def startup():
    create_store()
    slack_handler = AsyncSocketModeHandler(slack, settings.APP_TOKEN)
    await slack_handler.start_async()


def create_store() -> None:
    client = SpreadSheetClient()
    _create_store_path()
    _fetch_users(client)
    _fetch_contents(client)


def _create_store_path():
    try:
        os.mkdir("store")
    except FileExistsError:
        pass


def _fetch_users(client):
    users = client._users_data.get_values("A:D")
    with open("store/users.csv", "w") as f:
        f.writelines([f"{','.join(user)}\n" for user in users])


def _fetch_contents(client):
    contents = client._raw_data.get_values("A:H")
    with open("store/contents.csv", "w") as f:
        f.writelines([f"{content}" for content in _parse(contents)])


def _parse(contents: list[list[str]]) -> list[str]:
    result = []
    for content in contents:
        content[7] = content[7].replace(",", "#")
        result.append(",".join(content).replace("\n", " ") + "\n")
    return result
