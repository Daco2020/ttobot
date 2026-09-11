"""슬랙 AsyncApp 생성 테스트 (worklog 022).

slack_bolt 은 SLACK_CLIENT_ID / SLACK_CLIENT_SECRET 가 **환경변수로 존재하면** 파일 기반 OAuth
설치(다중 워크스페이스) 모드를 스스로 켠다(slack_bolt async_app.py). 또봇은 단일 워크스페이스
봇 토큰으로 동작하고 두 값은 웹 로그인용이다. 옛 서버는 .env 파일로만 읽어 환경변수가 없었지만
Koyeb 는 진짜 환경변수라, 설치 기록을 찾다가 모든 요청이 "reinstall this app" 으로 실패했다
(2026-09-11 컷오버 장애).
"""

from __future__ import annotations

import os

from app.slack.event_handler import create_slack_app

OAUTH_ENV = {"SLACK_CLIENT_ID": "111.222", "SLACK_CLIENT_SECRET": "dummy-secret"}


def test_oauth_env_does_not_enable_installation_store(monkeypatch) -> None:
    """⚠️ 두 값이 환경변수여도 OAuth 설치 모드가 켜지지 않는다 (Koyeb 조건 재현)."""
    for k, v in OAUTH_ENV.items():
        monkeypatch.setenv(k, v)

    app = create_slack_app()

    assert app.oauth_flow is None
    assert app.installation_store is None


def test_env_vars_are_restored_after_creation(monkeypatch) -> None:
    """✅ 생성 뒤 환경변수는 그대로 남는다 (설정 로더·다른 코드에 영향 없음)."""
    for k, v in OAUTH_ENV.items():
        monkeypatch.setenv(k, v)

    create_slack_app()

    assert {k: os.environ.get(k) for k in OAUTH_ENV} == OAUTH_ENV


def test_without_oauth_env_behaves_like_old_server(monkeypatch) -> None:
    """🌀 환경변수가 없으면(옛 서버) 기존과 같고, 없던 변수를 만들어 넣지도 않는다."""
    for k in OAUTH_ENV:
        monkeypatch.delenv(k, raising=False)

    app = create_slack_app()

    assert app.oauth_flow is None and app.installation_store is None
    assert all(k not in os.environ for k in OAUTH_ENV)


def test_env_restored_even_if_creation_fails(monkeypatch) -> None:
    """🌀 생성 중 예외가 나도 숨겼던 환경변수는 되돌린다."""
    for k, v in OAUTH_ENV.items():
        monkeypatch.setenv(k, v)

    def boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.slack.event_handler.AsyncApp", boom)
    try:
        create_slack_app()
    except RuntimeError:
        pass

    assert {k: os.environ.get(k) for k in OAUTH_ENV} == OAUTH_ENV
