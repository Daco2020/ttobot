from app.logging import logger

from zoneinfo import ZoneInfo
from app.client import SpreadSheetClient
from app.slack.repositories import SlackRepository
from fastapi import FastAPI, Request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import settings
from app.store import Store
from app.api.views.community import router as community_router
from app.api.views.login import router as login_router
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from fastapi.middleware.cors import CORSMiddleware
from app.slack.services import SlackReminderService


from slack_bolt.async_app import AsyncApp
from app.slack.event_handler import app as slack_app

# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from app.constants import DUE_DATES
# from datetime import datetime, time


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

slack_handler = AsyncSocketModeHandler(slack_app, settings.SLACK_APP_TOKEN)


@app.get("/")
async def health(request: Request) -> bool:
    return True


app.include_router(community_router, prefix="/v1")
app.include_router(login_router, prefix="/v1")

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

        trigger = IntervalTrigger(minutes=1, timezone=ZoneInfo("Asia/Seoul"))
        schedule.add_job(upload_logs, trigger=trigger, args=[store])

        schedule.start()

        # 리마인드 스케줄러(비동기)
        # TODO: 추후 10기에 활성화
        # first_remind_date = datetime.combine(
        #     DUE_DATES[0], time(hour=10, minute=0), tzinfo=ZoneInfo("Asia/Seoul")
        # )
        # last_remind_date = datetime.combine(
        #     DUE_DATES[10], time(hour=10, minute=0), tzinfo=ZoneInfo("Asia/Seoul")
        # )

        # async_schedule = AsyncIOScheduler()
        # remind_trigger = IntervalTrigger(
        #     weeks=2, start_date=first_remind_date, end_date=last_remind_date, timezone="Asia/Seoul"
        # )
        # async_schedule.add_job(remind_job, trigger=remind_trigger, args=[slack_app])

        # async_schedule.start()

        # 슬랙 소켓 모드 실행
        await slack_handler.connect_async()

    def upload_contents(store: Store) -> None:
        try:
            store.upload_queue()
        except Exception as e:
            logger.error(f"시트 업로드 중 에러 발생: {str(e)}")

    def upload_logs(store: Store) -> None:
        store.bulk_upload("logs")
        store.initialize_logs()

    async def remind_job(slack_app: AsyncApp) -> None:
        slack_service = SlackReminderService(repo=SlackRepository())
        await slack_service.send_reminder_message_to_user(slack_app)

    @app.on_event("shutdown")
    async def shutdown():
        # 서버 저장소 업로드
        store = Store(client=SpreadSheetClient())
        store.bulk_upload("logs")
        store.upload_queue()

else:

    @app.on_event("startup")
    async def startup():
        # 슬랙 소켓 모드 실행
        await slack_handler.connect_async()
