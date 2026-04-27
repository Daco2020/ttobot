"""app/api/auth.py 단위 테스트.

대상:
- encode_token / decode_token (pure JWT helpers)
- current_user (FastAPI dependency)
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api import auth as auth_module
from app.api.auth import current_user, decode_token, encode_token
from app.config import settings
from test import factories


# ---------------------------------------------------------------------------
# encode_token / decode_token
# ---------------------------------------------------------------------------


def test_encode_then_decode_round_trips_payload() -> None:
    """✅ 인코드 → 디코드 시 user_id, iss 가 보존된다."""
    # given
    payload: dict = {"user_id": "U_TEST"}

    # when
    token = encode_token(payload=dict(payload), expires_delta=timedelta(days=1))
    decoded = decode_token(token)

    # then
    assert decoded["user_id"] == "U_TEST"
    assert decoded["iss"] == "ttobot"
    assert "iat" in decoded
    assert "exp" in decoded
    assert decoded["exp"] > decoded["iat"]


def test_encode_token_round_trips_korean_and_special_chars() -> None:
    """🌀 한글/특수문자가 포함된 페이로드도 round-trip 보존."""
    # given
    payload = {"user_id": "U_TEST", "name": "김은찬", "memo": "🚀 테스트 #1"}

    # when
    token = encode_token(payload=dict(payload), expires_delta=timedelta(days=1))
    decoded = decode_token(token)

    # then
    assert decoded["user_id"] == "U_TEST"
    assert decoded["name"] == "김은찬"
    assert decoded["memo"] == "🚀 테스트 #1"


def test_decode_token_with_expired_token_raises() -> None:
    """⚠️ 만료된 토큰은 디코딩 시 예외 발생."""
    # given - 음수 expires_delta로 이미 만료된 토큰을 만든다.
    token = encode_token(
        payload={"user_id": "U_TEST"},
        expires_delta=timedelta(seconds=-1),
    )

    # when / then
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)


def test_decode_token_with_wrong_secret_raises() -> None:
    """⚠️ 잘못된 서명을 가진 토큰은 예외 발생."""
    # given - 다른 secret 으로 직접 만든 토큰
    fake_token = jwt.encode(
        {"user_id": "U_TEST", "iss": "ttobot"},
        "WRONG_SECRET",
        algorithm="HS256",
    )

    # when / then
    with pytest.raises(jwt.InvalidSignatureError):
        decode_token(fake_token)


def test_decode_token_with_wrong_issuer_raises() -> None:
    """⚠️ iss 가 다르면 예외 발생."""
    # given
    fake_token = jwt.encode(
        {"user_id": "U_TEST", "iss": "not_ttobot"},
        settings.SECRET_KEY,
        algorithm="HS256",
    )

    # when / then
    with pytest.raises(jwt.InvalidIssuerError):
        decode_token(fake_token)


# ---------------------------------------------------------------------------
# current_user dependency
# ---------------------------------------------------------------------------


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture
def fake_repo():
    """ApiRepository.get_user 만 흉내내는 mock."""
    return MagicMock()


@pytest.mark.asyncio
async def test_current_user_returns_simple_user_for_valid_token(fake_repo) -> None:
    """✅ 정상 access 토큰 + 유저 존재 → SimpleUser 반환."""
    # given
    user = factories.make_user(user_id="U_OK", name="정상유저")
    fake_repo.get_user.return_value = user
    token = encode_token(payload={"user_id": "U_OK"}, expires_delta=timedelta(days=1))

    # when
    result = await current_user(credentials=_bearer(token), api_repo=fake_repo)

    # then
    fake_repo.get_user.assert_called_once_with("U_OK")
    assert result.user_id == "U_OK"
    assert result.name == "정상유저"


@pytest.mark.asyncio
async def test_current_user_without_credentials_raises_403(fake_repo) -> None:
    """⚠️ Authorization 헤더 없음 → 403."""
    # when / then
    with pytest.raises(HTTPException) as exc_info:
        await current_user(credentials=None, api_repo=fake_repo)
    assert exc_info.value.status_code == 403
    assert "토큰이 존재하지 않습니다" in exc_info.value.detail
    fake_repo.get_user.assert_not_called()


@pytest.mark.asyncio
async def test_current_user_with_invalid_token_raises_403(fake_repo) -> None:
    """⚠️ 토큰 디코딩 실패 → 403."""
    # given - 완전히 형식이 깨진 토큰
    bad_token = "not.a.real.jwt"

    # when / then
    with pytest.raises(HTTPException) as exc_info:
        await current_user(credentials=_bearer(bad_token), api_repo=fake_repo)
    assert exc_info.value.status_code == 403
    assert "토큰이 유효하지 않습니다" in exc_info.value.detail
    fake_repo.get_user.assert_not_called()


@pytest.mark.asyncio
async def test_current_user_rejects_refresh_typed_token(fake_repo) -> None:
    """⚠️ refresh 타입 토큰을 access 로 사용 → 403."""
    # given
    refresh_token = encode_token(
        payload={"user_id": "U_OK", "type": "refresh"},
        expires_delta=timedelta(days=7),
    )

    # when / then
    with pytest.raises(HTTPException) as exc_info:
        await current_user(credentials=_bearer(refresh_token), api_repo=fake_repo)
    assert exc_info.value.status_code == 403
    assert "토큰이 유효하지 않습니다" in exc_info.value.detail
    fake_repo.get_user.assert_not_called()


@pytest.mark.asyncio
async def test_current_user_returns_404_when_user_not_found(fake_repo) -> None:
    """⚠️ 디코딩은 성공했지만 유저가 없는 경우 → 404."""
    # given
    fake_repo.get_user.return_value = None
    token = encode_token(payload={"user_id": "U_GHOST"}, expires_delta=timedelta(days=1))

    # when / then
    with pytest.raises(HTTPException) as exc_info:
        await current_user(credentials=_bearer(token), api_repo=fake_repo)
    assert exc_info.value.status_code == 404
    assert "유저가 존재하지 않습니다" in exc_info.value.detail


@pytest.mark.asyncio
async def test_current_user_with_empty_user_id_returns_404(fake_repo) -> None:
    """🌀 user_id 가 빈 문자열이면 repo 조회 자체를 안 하고 404."""
    # given - encode 후에도 user_id 가 "" 인 토큰
    token = encode_token(payload={"user_id": ""}, expires_delta=timedelta(days=1))

    # when / then
    with pytest.raises(HTTPException) as exc_info:
        await current_user(credentials=_bearer(token), api_repo=fake_repo)
    assert exc_info.value.status_code == 404
    fake_repo.get_user.assert_not_called()


def test_module_exposes_helpers_for_login_router() -> None:
    """sanity: login.py 에서 import 하는 심볼들이 살아있는지."""
    assert hasattr(auth_module, "encode_token")
    assert hasattr(auth_module, "decode_token")
    assert hasattr(auth_module, "current_user")
