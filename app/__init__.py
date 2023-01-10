import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from app.views import slack

load_dotenv()


api = FastAPI()


@api.on_event("startup")
async def startup():
    slack_handler = AsyncSocketModeHandler(slack, os.environ.get("APP_TOKEN"))
    await slack_handler.start_async()


@api.post("/")
async def health(request: Request) -> bool:
    return True
