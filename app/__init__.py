from typing import Any
from zoneinfo import ZoneInfo
from app.client import SpreadSheetClient
from fastapi import FastAPI, Request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import settings
from app.store import Store
from app.slack import event_handler
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler

app = FastAPI()
slack_handler = AsyncSocketModeHandler(event_handler.app, settings.APP_TOKEN)


@app.get("/")
async def health(request: Request) -> dict[str, Any]:
    return {"health": True}


if settings.ENV == "prod":

    @app.on_event("startup")
    async def startup():
        # 서버 저장소 동기화
        store = Store(client=SpreadSheetClient())
        store.pull()
        store.initialize_logs()

        # 업로드 스케줄러
        schedule = BackgroundScheduler(daemon=True, timezone="Asia/Seoul")
        schedule.add_job(upload_contents, "interval", seconds=10, args=[store])

        trigger = IntervalTrigger(minutes=10, timezone=ZoneInfo("Asia/Seoul"))
        schedule.add_job(upload_logs, trigger=trigger, args=[store])
        schedule.start()

        # 슬랙 소켓 모드 실행
        await slack_handler.connect_async()

    def upload_contents(store: Store) -> None:
        store.upload_queue()

    def upload_logs(store: Store) -> None:
        store.upload("logs")
        store.initialize_logs()

    @app.on_event("shutdown")
    async def shutdown():
        # 서버 저장소 업로드
        store = Store(client=SpreadSheetClient())
        store.upload("logs")
        store.upload_queue()

else:

    @app.on_event("startup")
    async def startup():
        # 슬랙 소켓 모드 실행
        await slack_handler.connect_async()
