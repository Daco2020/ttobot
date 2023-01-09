from fastapi import FastAPI
from app.views import router as v1_router

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello Geulttong"}


app.include_router(v1_router, prefix="/v1")
