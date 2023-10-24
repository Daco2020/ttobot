from zoneinfo import ZoneInfo
from app.client import SpreadSheetClient
from fastapi import FastAPI, Request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.config import settings
from app.store import Store
from app.slack import main
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler

app = FastAPI()
slack_handler = AsyncSocketModeHandler(main.app, settings.APP_TOKEN)


@app.post("/")
async def health(request: Request) -> bool:
    return True


if settings.ENV == "prod":

    @app.on_event("startup")
    async def startup():
        # 서버 저장소 동기화
        client = SpreadSheetClient()
        store = Store(client=client)
        store.sync()
        store.initialize_logs()

        # 업로드 스케줄러
        schedule = BackgroundScheduler(daemon=True, timezone="Asia/Seoul")
        schedule.add_job(upload_contents, "interval", seconds=10, args=[client])

        trigger = CronTrigger(hour=1, timezone=ZoneInfo("Asia/Seoul"))
        schedule.add_job(upload_logs, trigger=trigger, args=[store])
        schedule.start()

        # 슬랙 소켓 모드 실행
        await slack_handler.connect_async()

    def upload_contents(client: SpreadSheetClient) -> None:
        client.upload()

    def upload_logs(store: Store) -> None:
        store.upload("logs.csv")
        store.initialize_logs()

    @app.on_event("shutdown")
    async def shutdown():
        # 서버 저장소 업로드
        client = SpreadSheetClient()
        client.upload()
        store = Store(client=client)
        store.upload("logs.csv")

else:

    @app.on_event("startup")
    async def startup():
        # 슬랙 소켓 모드 실행
        await slack_handler.connect_async()
