import os
from app.client import SpreadSheetClient
from app.config import settings
from fastapi import FastAPI, Request
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
from app.views import slack


api = FastAPI()


@api.post("/")
async def health(request: Request) -> bool:
    return True


@api.on_event("startup")
async def startup():
    client = SpreadSheetClient()
    sync_store(client)
    schedule = BackgroundScheduler(daemon=True, timezone="Asia/Seoul")
    schedule.add_job(scheduler, "interval", seconds=10, args=[client])
    schedule.start()
    slack_handler = AsyncSocketModeHandler(slack, settings.APP_TOKEN)
    await slack_handler.start_async()


def sync_store(client: SpreadSheetClient) -> None:
    """서버 스토어를 동기화합니다."""
    create_store_path()
    client.sync_users()
    client.sync_contents()


def create_store_path():
    try:
        os.mkdir("store")
    except FileExistsError:
        pass


def scheduler(client: SpreadSheetClient) -> None:
    client.upload()
