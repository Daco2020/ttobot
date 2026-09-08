import asyncio
import traceback

from app.bigquery.client import BigqueryClient
from app.bigquery.queue import BigqueryQueue
from app.logging import logger

from zoneinfo import ZoneInfo
from app.client import SpreadSheetClient
from app.slack.repositories import SlackRepository
from fastapi import FastAPI, Request
from apscheduler.triggers.interval import IntervalTrigger
from app.keepalive import keepalive_job
from app.config import settings
from app.store import SheetQuotaExceeded, Store, flush_alerts, next_prev_deferred
from app.api.views.contents import router as contents_router
from app.api.views.login import router as login_router
from app.api.views.paper_planes import router as paper_planes_router
from app.api.views.point import router as point_router
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
app.include_router(message_router, prefix="/v1")
app.include_router(writing_participation_router, prefix="/v1")

if settings.ENV == "prod":
    async_schedule = AsyncIOScheduler(daemon=True, timezone=ZoneInfo("Asia/Seoul"))
    _flush_state = {"prev_deferred": False}

    async def _notify_admin(text: str) -> None:
        await slack_app.client.chat_postMessage(
            channel=settings.ADMIN_CHANNEL, text=text
        )

    @app.on_event("startup")
    async def startup():
        # 서버 저장소 동기화
        store = Store(client=SpreadSheetClient())

        # 저장소 복원: 로컬 CSV 가 없거나 비어 있는 테이블만 시트에서 가져온다.
        # (Koyeb 처럼 재배치마다 디스크가 초기화되는 환경 대응. 파일이 있으면 덮어쓰지 않는다)
        # 실패하면 startup 을 실패시킨다(fail-closed). Koyeb 는 새 배포가 healthy 면 옛 배포를
        # 죽이므로 데이터 없는 봇이 healthy 로 뜨면 정상이던 옛 배포가 사라진다. unhealthy 면
        # 옛 배포가 계속 서비스하고 Koyeb 가 재시작(3회)한다. (사용자 결정 2026-09-08, 019 뒤집음)
        try:
            restored = await asyncio.to_thread(store.restore_missing_tables)
            if restored:
                logger.info(f"시트에서 복원한 테이블: {restored}")
        except Exception as e:
            message = f"🫢 시트에서 저장소 복원에 실패해 부팅을 중단해요. {e}"
            logger.error(message)
            try:
                await _notify_admin(message)
            except Exception as notify_error:
                logger.error(f"복원 실패 알림 전송 실패: {notify_error}")
            raise

        # # 업로드 스케줄러
        async_schedule.add_job(
            upload_queue, "interval", seconds=20, args=[store, slack_app]
        )

        # 로그 업로드 스케줄러 (비활성화)
        # log_trigger = IntervalTrigger(minutes=1, timezone=ZoneInfo("Asia/Seoul"))
        # async_schedule.add_job(upload_logs, trigger=log_trigger, args=[store])

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
            subscribe_job,
            trigger=subscribe_trigger,
            args=[slack_app],
            # 0.1 vCPU 에서 08:00:00 을 1초만 넘겨도 기본 grace(1초)로 그날 잡이 건너뛰어진다
            misfire_grace_time=3600,
        )

        # self-ping 스케줄러: 5분마다 자기 공개 URL 을 GET 해 인바운드 트래픽을 만든다.
        # (Koyeb 무료 인스턴스의 1시간 유휴 scale-to-zero 방지. KOYEB_URL 미설정 시 비활성)
        if settings.KOYEB_URL:
            ping_trigger = IntervalTrigger(minutes=5, timezone=ZoneInfo("Asia/Seoul"))
            async_schedule.add_job(
                keepalive_job,
                trigger=ping_trigger,
                args=[settings.KOYEB_URL, _notify_admin],
            )
        else:
            logger.warning("KOYEB_URL 미설정: self-ping 비활성")

        # 스케줄러 시작
        async_schedule.start()

        # 슬랙 소켓 모드 실행
        await slack_handler.connect_async()

    async def upload_queue(store: Store, slack_app: AsyncApp) -> None:
        """업로드 큐에 있는 데이터를 업로드합니다."""
        try:
            report = await store.upload_queue()
        except SheetQuotaExceeded as e:
            # 429 는 틱 단위 백오프. 3회 이상 지속될 때만 관리자에게 알린다 (스팸 방지).
            logger.warning(str(e))
            for text in flush_alerts(error=e):
                await _notify_admin(text)
            return
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
            return

        # 못 찾아 버린 갱신 / 이월 시작 은 관리자에게 알린다.
        for text in flush_alerts(
            report=report, prev_deferred=_flush_state["prev_deferred"]
        ):
            await _notify_admin(text)
        _flush_state["prev_deferred"] = next_prev_deferred(
            report, _flush_state["prev_deferred"]
        )

    async def upload_logs(store: Store) -> None:
        """로그를 시트에 업로드하지 않고 로그 파일만 초기화합니다."""
        # store.upload_all("logs")
        store.initialize_logs()

    async def upload_bigquery(queue: BigqueryQueue) -> None:
        try:
            logger.info("BigQuery 업로드 작업 시작")
            await queue.upload()
            logger.info("BigQuery 업로드 작업 완료")
        except Exception as e:
            trace = traceback.format_exc()
            error = f"빅쿼리 업로드 중 에러가 발생했어요. {str(e)}"
            message = f"🫢 BigQuery 업로드 에러\n에러: {str(e)}\n\n트레이스:\n{trace}"
            logger.error(f"BigQuery 업로드 실패: {error}\n{trace}")

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
        # 마지막 flush 는 백오프 창 안이어도 한 번 시도한다. 실패해도(429 등) 뒤의
        # BigQuery 업로드·스케줄러 종료는 계속 진행한다.
        try:
            await store.upload_queue(force=True)
        except Exception as e:
            logger.error(f"종료 시 시트 flush 실패: {type(e).__name__}: {e}")
        # store.upload_all("logs")
        store.initialize_logs()

        queue = BigqueryQueue(client=BigqueryClient())
        await queue.upload()

        async_schedule.shutdown(wait=True)

else:

    @app.on_event("startup")
    async def startup():
        # 슬랙 소켓 모드 실행
        await slack_handler.connect_async()
