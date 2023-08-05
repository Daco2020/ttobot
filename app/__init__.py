from app.client import SpreadSheetClient
from fastapi import FastAPI, Request
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
from app.store import fetch_store
from app.slack_handler import SlackSocketModeHandler  # type: ignore
from app.views import slack


api = FastAPI()
slack_handler = SlackSocketModeHandler(slack)


@api.post("/")
async def health(request: Request) -> bool:
    return True


@api.on_event("startup")
async def startup():
    # 서버 저장소 동기화
    client = SpreadSheetClient()
    fetch_store(client)
    client.create_log_file()

    # 업로드 스케줄러
    schedule = BackgroundScheduler(daemon=True, timezone="Asia/Seoul")
    schedule.add_job(scheduler, "interval", seconds=10, args=[client])
    schedule.start()

    # 슬랙 소켓 모드 실행
    slack_handler.start()


def scheduler(client: SpreadSheetClient) -> None:
    client.upload()


@api.on_event("shutdown")
async def shutdown():
    # 서버 저장소 업로드
    client = SpreadSheetClient()
    client.upload()

    # 슬랙 소켓 모드 종료
    slack_handler.stop()
