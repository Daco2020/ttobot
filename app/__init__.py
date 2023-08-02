import asyncio
import threading
from app.client import SpreadSheetClient
from app.config import settings
from fastapi import FastAPI, Request
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
from app.db import fetch_db  # type: ignore
from app.views import slack


api = FastAPI()

socket_thread = None  # 전역 변수로 스레드를 관리
slack_handler = None
socket_mode_loop = asyncio.new_event_loop()


@api.post("/")
async def health(request: Request) -> bool:
    return True


def run_socket_mode():
    global slack_handler, socket_mode_loop
    asyncio.set_event_loop(socket_mode_loop)
    slack_handler = AsyncSocketModeHandler(slack, settings.APP_TOKEN)
    socket_mode_loop.run_until_complete(slack_handler.start_async())


@api.on_event("startup")
async def startup():
    # 서버 저장소 동기화
    client = SpreadSheetClient()
    fetch_db(client)
    client.create_log_file()

    # 업로드 스케줄러
    schedule = BackgroundScheduler(daemon=True, timezone="Asia/Seoul")
    schedule.add_job(scheduler, "interval", seconds=10, args=[client])
    schedule.start()

    # 슬랙 소켓 모드 실행
    global socket_thread
    socket_thread = threading.Thread(target=run_socket_mode, daemon=True)
    socket_thread.start()


def scheduler(client: SpreadSheetClient) -> None:
    client.upload()


def close_socket_mode():
    # 슬랙 소켓 모드는 다른 스레드를 사용하기 때문에 종료 함수를 소켓 모드 이벤트 루프에 콜백(전달)합니다.
    global slack_handler, socket_mode_loop
    socket_mode_loop.call_soon_threadsafe(
        socket_mode_loop.create_task, slack_handler.close_async()
    )


@api.on_event("shutdown")
async def shutdown():
    client = SpreadSheetClient()
    client.upload()

    # 슬랙 소켓 모드 종료
    global socket_thread
    if socket_thread is not None:
        close_thread = threading.Thread(target=close_socket_mode, daemon=True)
        close_thread.start()
        close_thread.join()
