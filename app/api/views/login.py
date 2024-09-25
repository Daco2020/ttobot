from datetime import timedelta
from typing import cast
from slack_bolt import BoltRequest
from app import models
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from app.api.auth import encode_token
from app.api.auth import current_user
from app.config import settings
from fastapi.responses import RedirectResponse
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.state_store import FileOAuthStateStore
from slack_bolt.oauth.oauth_flow import OAuthFlow

router = APIRouter()

oauth_settings = OAuthSettings(
    client_id=settings.SLACK_CLIENT_ID,
    client_secret=settings.SLACK_CLIENT_SECRET,
    scopes=["channels:read", "groups:read", "chat:write"],
    state_store=FileOAuthStateStore(expiration_seconds=600, base_dir="./data/states"),
    user_scopes=["identity.basic"],
    redirect_uri=f"https://{settings.CLEINT_DOMAIN}/slack/callback",
)

oauth_flow = OAuthFlow(settings=oauth_settings)


@router.get("/slack/login")
async def slack_login(request: Request):
    state = oauth_flow.issue_new_state(request=cast(BoltRequest, request))
    url = oauth_settings.authorize_url_generator.generate(state=state)
    return RedirectResponse(url=url)


@router.get("/slack/auth")
async def slack_auth(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if error:
        raise HTTPException(status_code=404, detail=f"Slack OAuth Error: {error}")

    if not code:
        raise HTTPException(
            status_code=403, detail="Slack OAuth Error: Invalid authentication code"
        )

    result = oauth_flow.run_installation(code=code)
    if not result:
        raise HTTPException(
            status_code=403, detail="Slack OAuth Error: Failed to run installation"
        )

    token = encode_token(
        payload={"user_id": result.user_id}, expires_delta=timedelta(days=1)
    )
    return JSONResponse(
        status_code=200, content={"access_token": token, "message": "success"}
    )


@router.get("/test-login")
async def test_login(user: models.User = Depends(current_user)):
    """
    로그인 테스트용 API 입니다.
    로그인에 성공한다면 유저 정보를 반환합니다.
    """
    return user
