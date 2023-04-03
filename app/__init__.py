from app.client import SpreadSheetClient
from app.config import settings
from fastapi import FastAPI, Request
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
from app.db import sync_db  # type: ignore
from app.views import slack

api = FastAPI()


@api.post("/")
async def health(request: Request) -> bool:
    return True


@api.on_event("startup")
async def startup():
    client = SpreadSheetClient()
    client.create_log_file()
    sync_db(client)
    schedule = BackgroundScheduler(daemon=True, timezone="Asia/Seoul")
    schedule.add_job(scheduler, "interval", seconds=10, args=[client])
    schedule.start()
    slack_handler = AsyncSocketModeHandler(slack, settings.APP_TOKEN)
    await slack_handler.start_async()


def scheduler(client: SpreadSheetClient) -> None:
    client.upload()
