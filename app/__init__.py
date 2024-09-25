import traceback

# from app.bigquery.client import BigqueryClient
from app.bigquery.queue import BigqueryQueue
from app.logging import logger

from zoneinfo import ZoneInfo
from app.client import SpreadSheetClient
from app.slack.repositories import SlackRepository
from fastapi import FastAPI, Request
from apscheduler.triggers.interval import IntervalTrigger
from app.config import settings
from app.store import Store
from app.api.views.contents import router as contents_router
from app.api.views.login import router as login_router
from app.api.views.paper_airplanes import router as paper_airplanes_router
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from fastapi.middleware.cors import CORSMiddleware
from app.slack.services.background import BackgroundService


from slack_bolt.async_app import AsyncApp
from app.slack.event_handler import app as slack_app

from apscheduler.schedulers.asyncio import AsyncIOScheduler

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

slack_handler = AsyncSocketModeHandler(
    app=slack_app,
    app_token=settings.SLACK_APP_TOKEN,
)


@app.get("/")
async def health(request: Request) -> bool:
    return True


app.include_router(contents_router, prefix="/v1")
app.include_router(login_router, prefix="/v1")
app.include_router(paper_airplanes_router, prefix="/v1")

if settings.ENV == "prod":
    async_schedule = AsyncIOScheduler(daemon=True, timezone=ZoneInfo("Asia/Seoul"))

    @app.on_event("startup")
    async def startup():
        # 서버 저장소 동기화
        store = Store(client=SpreadSheetClient())
        store.pull()
        store.initialize_logs()

        # 업로드 스케줄러
        async_schedule.add_job(
            upload_queue, "interval", seconds=10, args=[store, slack_app]
        )

        trigger = IntervalTrigger(minutes=1, timezone=ZoneInfo("Asia/Seoul"))
        async_schedule.add_job(upload_logs, trigger=trigger, args=[store])

        # TODO: 추후 10기에 활성화
        # queue = BigqueryQueue(client=BigqueryClient())
        # trigger = IntervalTrigger(seconds=30, timezone=ZoneInfo("Asia/Seoul"))
        # async_schedule.add_job(upload_bigquery, trigger=trigger, args=[queue])

        # 리마인드 스케줄러
        # TODO: 추후 10기에 활성화
        # first_remind_date = datetime.combine(
        #     DUE_DATES[0], time(hour=10, minute=0), tzinfo=ZoneInfo("Asia/Seoul")
        # )
        # last_remind_date = datetime.combine(
        #     DUE_DATES[10], time(hour=10, minute=0), tzinfo=ZoneInfo("Asia/Seoul")
        # )

        # remind_trigger = IntervalTrigger(
        #     weeks=2, start_date=first_remind_date, end_date=last_remind_date, timezone="Asia/Seoul"
        # )
        # async_schedule.add_job(remind_job, trigger=remind_trigger, args=[slack_app])

        async_schedule.start()

        # 슬랙 소켓 모드 실행
        await slack_handler.connect_async()

    async def upload_queue(store: Store, slack_app: AsyncApp) -> None:
        """업로드 큐에 있는 데이터를 업로드합니다."""
        try:
            await store.upload_queue()
        except Exception as e:
            trace = traceback.format_exc()
            error = f"시트 업로드 중 에러가 발생했어요. {str(e)} {trace}"
            message = f"🫢: {error=} 🕊️: {trace=}"
            logger.error(message)

            # 관리자에게 에러를 알립니다.
            await slack_app.client.chat_postMessage(
                channel=settings.ADMIN_CHANNEL,
                text=message,
            )

    async def upload_logs(store: Store) -> None:
        store.bulk_upload("logs")
        store.initialize_logs()

    async def upload_bigquery(queue: BigqueryQueue) -> None:
        try:
            await queue.upload()
        except Exception as e:
            trace = traceback.format_exc()
            error = f"빅쿼리 업로드 중 에러가 발생했어요. {str(e)} {trace}"
            message = f"🫢: {error=} 🕊️: {trace=}"
            logger.error(message)

            # 관리자에게 에러를 알립니다.
            await slack_app.client.chat_postMessage(
                channel=settings.ADMIN_CHANNEL,
                text=message,
            )

    async def remind_job(slack_app: AsyncApp) -> None:
        slack_service = BackgroundService(repo=SlackRepository())
        await slack_service.send_reminder_message_to_user(slack_app)

    @app.on_event("shutdown")
    async def shutdown():
        # 서버 저장소 업로드
        await slack_handler.close_async()

        store = Store(client=SpreadSheetClient())
        await store.upload_queue()
        store.bulk_upload("logs")
        store.initialize_logs()

        async_schedule.shutdown(wait=True)

else:

    @app.on_event("startup")
    async def startup():
        # 슬랙 소켓 모드 실행
        await slack_handler.connect_async()
