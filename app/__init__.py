from app.config import settings
from fastapi import FastAPI, Request
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from app.views import slack


api = FastAPI()
# TODO: 로킹 미들웨어 추가필요


@api.on_event("startup")
async def startup():
    slack_handler = AsyncSocketModeHandler(slack, settings.APP_TOKEN)
    await slack_handler.start_async()


@api.post("/")
async def health(request: Request) -> bool:
    return True
