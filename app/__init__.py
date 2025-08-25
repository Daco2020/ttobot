import traceback

from app.bigquery.client import BigqueryClient
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
from app.api.views.paper_planes import router as paper_planes_router
from app.api.views.point import router as point_router
from app.api.views.inflearn import router as inflearn_router
from app.api.views.message import router as message_router
from app.api.views.writing_participation import router as writing_participation_router
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from fastapi.middleware.cors import CORSMiddleware
from app.slack.services.background import BackgroundService


from slack_bolt.async_app import AsyncApp
from app.slack.event_handler import app as slack_app

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://geultto-post-board.netlify.app",
        "https://geultto-paper-plane.vercel.app",
        "http://localhost:3000",
    ],
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
app.include_router(paper_planes_router, prefix="/v1")
app.include_router(point_router, prefix="/v1")
app.include_router(inflearn_router, prefix="/v1")
app.include_router(message_router, prefix="/v1")
app.include_router(writing_participation_router, prefix="/v1")

if settings.ENV == "prod":
    async_schedule = AsyncIOScheduler(daemon=True, timezone=ZoneInfo("Asia/Seoul"))

    @app.on_event("startup")
    async def startup():
        # 서버 저장소 동기화
        store = Store(client=SpreadSheetClient())

        # # 업로드 스케줄러
        async_schedule.add_job(
            upload_queue, "interval", seconds=20, args=[store, slack_app]
        )

        # 로그 업로드 스케줄러
        log_trigger = IntervalTrigger(minutes=1, timezone=ZoneInfo("Asia/Seoul"))
        async_schedule.add_job(upload_logs, trigger=log_trigger, args=[store])

        # 빅쿼리 업로드 스케줄러
        bigquery_trigger = IntervalTrigger(minutes=10, timezone=ZoneInfo("Asia/Seoul"))
        queue = BigqueryQueue(client=BigqueryClient())
        async_schedule.add_job(upload_bigquery, trigger=bigquery_trigger, args=[queue])

        # 멤버 구독 알림 스케줄러: 매일 오전 8시
        subscribe_trigger = CronTrigger(
            hour=8,
            minute=0,
            timezone="Asia/Seoul",
        )
        async_schedule.add_job(
            subscribe_job, trigger=subscribe_trigger, args=[slack_app]
        )

        # 스케줄러 시작
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
        store.upload_all("logs")
        store.initialize_logs()

    async def upload_bigquery(queue: BigqueryQueue) -> None:
        try:
            await queue.upload()
        except Exception as e:
            trace = traceback.format_exc()
            error = f"빅쿼리 업로드 중 에러가 발생했어요. {str(e)} {trace}"
            message = f"🫢: {error=} 🕊️: {trace=}"
            logger.error(message)

            await slack_app.client.chat_postMessage(
                channel=settings.ADMIN_CHANNEL,
                text=message,
            )

    async def subscribe_job(slack_app: AsyncApp) -> None:
        slack_service = BackgroundService(repo=SlackRepository())
        try:
            await slack_service.prepare_subscribe_message_data()
            await slack_service.send_subscription_messages(slack_app)
        except Exception as e:
            trace = traceback.format_exc()
            error = f"멤버 구독 알림 전송 중 에러가 발생했어요. {str(e)} {trace}"
            message = f"🫢: {error=} 🕊️: {trace=}"
            logger.error(message)

            await slack_app.client.chat_postMessage(
                channel=settings.ADMIN_CHANNEL,
                text=message,
            )

    @app.on_event("shutdown")
    async def shutdown():
        # 서버 저장소 업로드
        await slack_handler.close_async()

        store = Store(client=SpreadSheetClient())
        await store.upload_queue()
        store.upload_all("logs")
        store.initialize_logs()

        queue = BigqueryQueue(client=BigqueryClient())
        await queue.upload()

        async_schedule.shutdown(wait=True)

else:

    @app.on_event("startup")
    async def startup():
        # 슬랙 소켓 모드 실행
        await slack_handler.connect_async()
