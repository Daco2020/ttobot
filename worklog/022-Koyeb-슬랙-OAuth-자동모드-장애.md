# 022 - Koyeb 에서 슬랙 OAuth 자동 모드로 모든 요청 실패

## 왜

컷오버(2026-09-11 13:43 옛 봇 정지, 13:52 Koyeb 기동) 직후 슬랙 명령마다
"your installation with this app is no longer available. Please reinstall" 응답.

## 문제

- Koyeb 로그: `Although the app should be installed ... AuthorizeResult ... was not found.`
  부팅 경고 2줄(`installation_store ... token will be ignored` 등)은 옛 서버 nohup.out 에 0회.
- slack_bolt 1.28 `AsyncApp.__init__`(async_app.py:293)은 `SLACK_CLIENT_ID`·`SLACK_CLIENT_SECRET` 가
  **환경변수로 있으면** 파일 기반 OAuth 설치 모드를 자동으로 켠다 → 설치 기록 조회 인증.
- 옛 서버는 두 값이 `.env` 파일로만 pydantic-settings 에 읽혀 `os.environ` 에 없었다. Koyeb 는 진짜 환경변수.
- 로컬 재현(가짜 값): 환경변수 없음 → OAuth 꺼짐 / 있음 → 켜짐 + 같은 경고.
- 사전 부팅 모의는 설정 로딩만 봤고, 라이브러리가 `os.environ` 을 직접 읽는 경로는 보지 못했다.

## 해결

- `event_handler.create_slack_app()`: `AsyncApp` 생성 동안만 두 환경변수를 숨기고 `finally` 로 복원.
  웹 로그인(`login.py`)은 두 값을 `settings` 에서 직접 받으므로 영향 없음.
- TDD: 동작 변화 없는 분리 후 OAuth 테스트 RED → 수정 후 GREEN. 4종(Koyeb 조건 · 복원 ·
  환경변수 없음 · 생성 실패 시 복원). 전체 346 passed.

## 결과

재배포 뒤 아래 검증으로 확인한다. 교훈: 설정을 파일에서 환경변수로 옮길 땐 **라이브러리가
`os.environ` 을 직접 읽는지**까지 확인해야 한다.

## 사용자 검증 방법

1. 재배포 로그에 `installation_store ... ignored` 와 `AuthorizeResult ... not found` 가 **없어야** 함
   (`client ... token will be unused` 는 무해해서 남음)
2. 슬랙 `/도움말` → 모달이 뜸. `/제출` 모달 하단이 글쓰기 채널인지(참여자 계정)
3. 엣지: 종이비행기 웹 로그인(두 값을 쓰는 곳)이 되는지

| 날짜 | 내용 |
| --- | --- |
| 2026-09-11 | 슬랙 앱 생성 중 OAuth 환경변수 숨김으로 자동 설치 모드 차단 |
