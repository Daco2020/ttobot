from app.client import SpreadSheetClient
from fastapi import FastAPI, Request
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import settings
from app.store import sync_store
from app import slack
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler

app = FastAPI()
slack_handler = AsyncSocketModeHandler(slack.app, settings.APP_TOKEN)


@app.post("/")
async def health(request: Request) -> bool:
    return True


if settings.ENV == "prod":

    @app.on_event("startup")
    async def startup():
        # 서버 저장소 동기화
        client = SpreadSheetClient()
        sync_store(client)
        client.create_log_file()

        # 업로드 스케줄러
        schedule = BackgroundScheduler(daemon=True, timezone="Asia/Seoul")
        schedule.add_job(scheduler, "interval", seconds=10, args=[client])
        schedule.start()

        # 슬랙 소켓 모드 실행
        await slack_handler.connect_async()

    def scheduler(client: SpreadSheetClient) -> None:
        client.upload()

    @app.on_event("shutdown")
    async def shutdown():
        # 서버 저장소 업로드
        client = SpreadSheetClient()
        client.upload()

else:

    @app.on_event("startup")
    async def startup():
        # 슬랙 소켓 모드 실행
        await slack_handler.connect_async()
