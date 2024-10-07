from datetime import timedelta
from typing import cast
from slack_bolt import BoltRequest
from app import models
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from app.api.auth import decode_token, encode_token
from app.api.auth import current_user
from app.api.deps import api_service
from app.api.services import ApiService
from app.config import settings
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.state_store import FileOAuthStateStore
from slack_bolt.oauth.oauth_flow import OAuthFlow
from jwt import PyJWTError

router = APIRouter()

oauth_settings = OAuthSettings(
    client_id=settings.SLACK_CLIENT_ID,
    client_secret=settings.SLACK_CLIENT_SECRET,
    scopes=["channels:read", "groups:read", "chat:write"],
    state_store=FileOAuthStateStore(expiration_seconds=600, base_dir="./data/states"),
    user_scopes=["identity.basic"],
    redirect_uri=f"https://{settings.CLIENT_DOMAIN}/slack/callback",
)

oauth_flow = OAuthFlow(settings=oauth_settings)


@router.get("/slack/login")
async def slack_login(request: Request):
    state = oauth_flow.issue_new_state(request=cast(BoltRequest, request))
    url = oauth_settings.authorize_url_generator.generate(state=state)
    return JSONResponse(content={"redirect_url": url})


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

    access_token = encode_token(
        payload={"user_id": result.user_id},
        expires_delta=timedelta(days=1),
    )
    refresh_token = encode_token(
        payload={"user_id": result.user_id, "type": "refresh"},
        expires_delta=timedelta(days=7),
    )
    return JSONResponse(
        status_code=200,
        content={
            "access_token": access_token,
            "refresh_token": refresh_token,
        },
    )


@router.post("/slack/auth/refresh")
async def slack_auth_refresh(
    refresh_token: str,
    service: ApiService = Depends(api_service),
):
    try:
        decoded_payload = decode_token(refresh_token)
        if decoded_payload.get("type") != "refresh":
            return HTTPException(status_code=403, detail="토큰이 유효하지 않습니다.")

        user = service.get_user_by(user_id=decoded_payload["user_id"])
        if not user:
            return HTTPException(status_code=404, detail="해당하는 유저가 없습니다.")

    except PyJWTError:
        return HTTPException(status_code=403, detail="토큰이 유효하지 않습니다.")

    access_token = encode_token(
        payload={"user_id": user.user_id}, expires_delta=timedelta(days=1)
    )
    return JSONResponse(
        status_code=200,
        content={
            "access_token": access_token,
        },
    )


@router.get("/slack/me")
async def get_me(user: models.SimpleUser = Depends(current_user)):
    """로그인 유저의 정보를 반환합니다."""
    return user
