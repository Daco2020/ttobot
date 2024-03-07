import jwt
from app import models
from app.config import settings


from fastapi import Cookie, Depends, HTTPException, Response


from datetime import datetime, timedelta, timezone
from typing import Any, cast
from app.deps import user_repo
from app.repositories import UserRepository

from app.utils import tz_now


def login(response: Response, payload: dict[str, Any]):
    token = encode_token(payload=payload, expires_delta=timedelta(days=1))
    set_cookie(response=response, key="access_token", value=token)


def set_cookie(
    response: Response,
    key: str,
    value: str,
) -> None:
    """응답에 쿠키를 설정합니다."""
    response.set_cookie(
        key=key,
        value=value,
        max_age=60 * 60 * 24,
        expires=datetime.now(timezone.utc) + timedelta(days=1),
        domain=settings.DOMAIN,
        path="/",
        httponly=True,
        secure=True,
    )


def encode_token(
    payload: dict[str, Any],
    expires_delta: timedelta,
    algorithm: str = "HS256",
) -> str:
    """토큰을 생성합니다."""
    payload["iss"] = "ttobot"
    payload["iat"] = iat = tz_now()
    payload["exp"] = iat + expires_delta
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=algorithm,
    )


def decode_token(
    token: str,
    algorithm: str = "HS256",
) -> dict[str, Any]:
    """토큰을 디코딩합니다."""
    options = {"verify_exp": True, "verify_iss": True}
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        issuer="ttobot",
        algorithms=[algorithm],
        options=options,
    )


async def current_user(
    user_repo: UserRepository = Depends(user_repo),
    access_token: str = Cookie(default=None),
) -> models.User:
    """현재 유저를 조회합니다."""
    if access_token:
        try:
            result = decode_token(access_token)
        except Exception:
            raise HTTPException(
                status_code=403, detail=f"토큰이 유효하지 않습니다. token: {access_token}"
            )

        if user_id := result.get("user_id", None):
            user = user_repo.get_user(cast(str, user_id))
        if not user_id or not user:
            raise HTTPException(
                status_code=404,
                detail=f"유저가 존재하지 않습니다. user_id: {result.get('user_id')}",
            )
        return user
    else:
        raise HTTPException(
            status_code=404, detail=f"토큰이 존재하지 않습니다. token: {access_token}"
        )
