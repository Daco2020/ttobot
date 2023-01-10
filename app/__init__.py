from fastapi import FastAPI
from pydantic import BaseModel
from app.views import router as v1_router

app = FastAPI()


class Event(BaseModel):
    token: str
    challenge: str
    type: str


@app.post("/")
async def verify(event: Event):
    return {"challenge": event.challenge}


app.include_router(v1_router, prefix="/v1")
