from app.client import SpreadSheetClient
from app.config import settings
from fastapi import FastAPI, Request
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
from app.db import fetch_db  # type: ignore
from app.views import slack


api = FastAPI()


@api.post("/")
async def health(request: Request) -> bool:
    return True


@api.post("/run-socket-mode")
async def run_socket_mode(request: Request) -> None:
    slack_handler = AsyncSocketModeHandler(slack, settings.APP_TOKEN)
    await slack_handler.start_async()


@api.on_event("startup")
async def startup():
    client = SpreadSheetClient()
    fetch_db(client)
    client.create_log_file()
    schedule = BackgroundScheduler(daemon=True, timezone="Asia/Seoul")
    schedule.add_job(scheduler, "interval", seconds=10, args=[client])
    schedule.start()


def scheduler(client: SpreadSheetClient) -> None:
    client.upload()


@api.on_event("shutdown")
async def shutdown():
    client = SpreadSheetClient()
    client.upload()
