# 또봇 테스트 보강 & 리팩터링 계획

이 문서는 또봇 프로젝트의 **백엔드 API 라우터**와 **슬랙 이벤트 핸들러**에 대한 테스트 코드를
빠짐없이(성공·실패·엣지) 작성하기 위한 계획서이다. 기능 변경은 최소화하고, 테스트가 가능한
구조로 다듬는 데 초점을 둔다.

---

## 1. 현재 구조 요약

### 1-1. 디렉터리 한눈에 보기

```
app/
├── __init__.py            # FastAPI 앱 + 슬랙 소켓모드 핸들러 + 스케줄러
├── api/                   # 백엔드 API 계층
│   ├── auth.py            # JWT 인코딩/디코딩, current_user 의존성
│   ├── deps.py            # FastAPI Depends 팩토리
│   ├── dto.py             # 응답/요청 DTO
│   ├── repositories.py    # CSV 기반 ApiRepository
│   ├── services.py        # ApiService (종이비행기 보내기 등)
│   └── views/             # 라우터 모음
│       ├── contents.py    # /v1/contents, /v1/messages
│       ├── inflearn.py    # /v1/inflearn/coupons
│       ├── login.py       # /v1/slack/login, /auth, /auth/refresh, /me
│       ├── message.py     # /v1/send-messages
│       ├── paper_planes.py# /v1/paper-planes (POST/GET)
│       ├── point.py       # /v1/points
│       └── writing_participation.py
├── slack/                 # 슬랙 봇 계층
│   ├── event_handler.py   # AsyncApp + 미들웨어 + 라우팅
│   ├── repositories.py    # CSV 기반 SlackRepository
│   ├── services/
│   │   ├── base.py        # SlackService
│   │   ├── point.py       # PointService
│   │   └── background.py  # 리마인더/구독 알림
│   ├── events/            # 핸들러 모음 (community/contents/core/log/subscriptions/writing_participation)
│   └── components/        # 슬랙 블록 컴포넌트
├── bigquery/              # BigQuery 클라이언트 + 큐
├── client.py              # 구글 시트 클라이언트
├── store.py               # 시트/CSV 동기화 큐
├── models.py              # Pydantic 모델 (User, Content, Bookmark, ...)
├── constants.py           # DUE_DATES, BOT_IDS, 색상맵 등
├── exception.py           # BotException, ClientException
└── utils.py               # tz_now, json 변환 등
store/                     # CSV 데이터 (실데이터)
test/                      # 기존 테스트 (point/reminder 만 있음)
```

### 1-2. 외부 의존성 지도

테스트에서는 모두 mock 또는 우회 대상이다.

| 분류        | 사용 위치                                          | 처리 방식                                |
| ----------- | -------------------------------------------------- | ---------------------------------------- |
| Slack API   | `slack_app.client.*`, `client.*` (핸들러 인자)     | `AsyncMock`/`mocker.patch.object`        |
| Google Sheets | `app/client.py`, `app/store.py`                  | 호출 자체를 mock (테스트는 큐에만 push)  |
| BigQuery    | `app/bigquery/*`                                   | 모듈 import 시 사이드 이펙트 없도록 mock |
| HTTP 외부   | `app/slack/services/base.py:get_title` (httpx)     | `httpx.AsyncClient` mock                 |
| googletrans | `app/utils.py:translate_keywords`                  | `translate_keywords` 자체를 mock         |
| 파일 시스템 | `store/*.csv` 다수 함수가 직접 read/write          | `tmp_path` + monkeypatch로 cwd 격리      |
| JWT         | `app/api/auth.py` `encode_token`/`decode_token`    | 실제 동작(secret 주입)                   |
| OAuth Flow  | `app/api/views/login.py:oauth_flow.run_installation` | mock                                    |

### 1-3. API 라우터 한눈에 보기

| Method | Path                       | 인증 | 권한        | 외부 의존  |
| ------ | -------------------------- | ---- | ----------- | ---------- |
| GET    | `/`                        | ✗    | -           | -          |
| GET    | `/v1/contents`             | ✗    | -           | CSV, googletrans |
| GET    | `/v1/messages`             | ✓    | ADMIN       | Slack API  |
| POST   | `/v1/messages`             | ✓    | ADMIN       | Slack API  |
| GET    | `/v1/slack/login`          | ✗    | -           | OAuth state store |
| GET    | `/v1/slack/auth`           | ✗    | -           | OAuth flow |
| GET    | `/v1/slack/auth/refresh`   | ✗    | -           | CSV (User) |
| GET    | `/v1/slack/me`             | ✓    | -           | CSV (User) |
| POST   | `/v1/paper-planes`         | ✓    | -           | CSV, Slack |
| GET    | `/v1/paper-planes/sent`    | ✓    | -           | CSV        |
| GET    | `/v1/paper-planes/received`| ✓    | -           | CSV        |
| POST   | `/v1/points`               | ✓    | ADMIN       | CSV, Slack |
| GET    | `/v1/inflearn/coupons`     | ✓    | ADMIN       | CSV        |
| POST   | `/v1/send-messages`        | ✓    | ADMIN       | Slack API  |
| GET    | `/v1/writing-participation`| ✗    | -           | CSV        |

### 1-4. 슬랙 이벤트 핸들러 한눈에 보기

`app/slack/event_handler.py` 의 등록만 추리면 다음과 같다.

- **미들웨어**
  - `log_event_middleware` — 이벤트 종류 분류 + 로그 기록
  - `dependency_injection_middleware` — `service`, `point_service`, `user` 컨텍스트 주입
  - `handle_error` — 에러 처리 + 관리자 채널 알림

- **이벤트**
  - `message` — 커피챗 인증 / 문의사항 알림 분기
  - `reaction_added`, `reaction_removed` — 빅쿼리 큐 적재 + 공지/성윤글 포인트
  - `app_mention`, `member_joined_channel`, `channel_created`, `app_home_opened`

- **명령어**: `/제출`, `/패스`, `/검색`, `/북마크`, `/예치금`, `/제출내역`, `/도움말`, `/관리자`, `/종이비행기`

- **액션 / 뷰**: 30+ 종 (글 제출, 북마크, 커피챗 인증, 구독, 종이비행기, 글쓰기 참여 신청 등)

---

## 2. 리팩터링 원칙

테스트를 작성하는 과정에서 필요한 최소한의 구조 정리만 수행한다. **기능 변경은 금지**.

1. **외부 의존성을 핸들러 인자로 명시**: `slack_app.client` 같은 전역 의존이 있으면, 가능한 경우 함수 인자로
   대체하고 테스트에서 fake 클라이언트를 주입한다. 이미 핸들러 함수들은 대부분 `client: AsyncWebClient`
   형태로 인자를 받으므로 추가 작업은 거의 없다.
2. **부수효과 제거 못 하는 import 격리**: `app/__init__.py` import 시점에 슬랙/스케줄러가 살아나지 않도록
   테스트에서는 환경 변수(ENV=dev) + 스케줄러 mock으로 대응한다. 코드 변경은 없다.
3. **`store` 디렉터리에 의존하는 함수**: 함수 시그니처는 그대로 두고, 테스트가 자신만의 임시 CSV
   디렉터리에서 동작하도록 `tmp_path` + `monkeypatch.chdir` 픽스처를 활용한다.
4. **공통 픽스처 정리**: `test/conftest.py`를 보강해 `make_user`, `slack_client_mock`, `tmp_store_dir`,
   `settings_override` 등의 헬퍼를 제공한다.
5. **신규 테스트 디렉터리 구조**:
   ```
   test/
   ├── conftest.py
   ├── factories.py            # 모델 팩토리 (User, Content, ...)
   ├── api/
   │   ├── conftest.py         # FastAPI TestClient + 토큰 헬퍼
   │   ├── test_auth.py
   │   ├── test_contents.py
   │   ├── test_inflearn.py
   │   ├── test_login.py
   │   ├── test_message.py
   │   ├── test_paper_planes.py
   │   ├── test_point.py
   │   └── test_writing_participation.py
   └── slack/
       ├── conftest.py
       ├── test_community_events.py
       ├── test_contents_events.py
       ├── test_core_events.py
       ├── test_log_events.py
       ├── test_subscriptions_events.py
       ├── test_writing_participation_events.py
       └── test_event_handler_middlewares.py
   ```
   기존 `test_point.py`, `test_reminder.py`는 각각 `test/services/` 또는 적절한 위치로 옮겨 정리한다.

---

## 3. 도구 / 환경 전환 (uv)

### 3-1. 목표

- `pip + venv` 기반 → `uv` 기반으로 전환
- 의존성 락 파일(`uv.lock`)로 재현 가능성 확보
- `requirements.txt`는 호환을 위해 `uv export`로 자동 생성 가능

### 3-2. 작업 순서

1. `pyproject.toml` 신규 작성. `[project]` 섹션에 패키지명/파이썬 버전/런타임 의존성을
   `requirements.txt`에서 옮겨 적되, **버전은 호환 범위(`>=`)** 로 일부 풀어준다(특히 dev only 계열).
2. `[dependency-groups]` 또는 `[tool.uv]`의 dev 그룹에 `pytest`, `pytest-asyncio`, `pytest-mock`,
   `pytest-sugar`, `httpx` (FastAPI TestClient용)를 분리.
3. `uv sync`로 `.venv` 생성 및 락 파일 생성.
4. `Makefile`의 `install`, `freeze`, `dev`, `prod` 타겟을 `uv run` / `uv sync` 로 갱신.
5. `.python-version`을 실제 버전(`3.11`)으로 교체.
6. `requirements.txt`는 우선 유지(외부 배포용). 추후 `uv export --format requirements-txt` 로 갱신 가능.

### 3-3. 신규 `pyproject.toml` 골격 (안)

```toml
[project]
name = "ttobot"
version = "0.1.0"
description = "글또 슬랙 봇 + 백엔드 서버"
requires-python = ">=3.11,<3.13"
dependencies = [
    # 핵심 런타임
    "fastapi>=0.109,<0.116",
    "uvicorn>=0.20",
    "slack-bolt>=1.16",
    "slack-sdk>=3.19",
    "pydantic>=2.6",
    "pydantic-settings>=2.1",
    "PyJWT>=2.9",
    # 데이터/유틸
    "pandas>=2.1",
    "polars>=0.19",
    "orjson>=3.8",
    "regex>=2023.12",
    "tenacity>=9.0",
    "loguru>=0.7",
    "aiocache>=0.12",
    "httpx>=0.13",
    "beautifulsoup4>=4.12",
    "googletrans==4.0.0rc1",
    "APScheduler>=3.10",
    # 구글/빅쿼리
    "gspread>=5.7",
    "google-cloud-bigquery>=3.25",
    "pandas-gbq>=0.23",
    "pyarrow>=17.0",
    "db-dtypes>=1.3",
    # 기타
    "python-dotenv>=0.21",
    "requests>=2.28",
]

[dependency-groups]
dev = [
    "pytest>=7.4",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.12",
    "pytest-sugar>=0.9",
    "httpx>=0.13",          # TestClient 의존
    "ruff",
    "mypy>=1.8",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["test"]
```

---

## 4. 단계별 작업 흐름 (사용자와 함께 진행)

리팩터링이라기보단 "테스트 환경 정비 → 테스트 추가" 흐름. 한 단계씩 사용자 확인을 받고 진행한다.

| 단계 | 내용                                                           | 산출물                         |
| ---- | -------------------------------------------------------------- | ------------------------------ |
| 0    | 본 문서 + 02-test-todo 작성                                    | docs/01, docs/02               |
| 1    | uv 환경 셋업 (pyproject.toml, uv.lock, .python-version, Makefile) | uv 기반 가상환경              |
| 2    | 테스트용 conftest, settings 픽스처, 모델 팩토리 정비            | `test/conftest.py`, `test/factories.py` |
| 3    | API 테스트 — 인증/유저 (`auth`, `login`, `me`)                  | `test/api/test_login.py` 등    |
| 4    | API 테스트 — 종이비행기                                         | `test/api/test_paper_planes.py`|
| 5    | API 테스트 — 콘텐츠/메시지                                      | `test/api/test_contents.py`    |
| 6    | API 테스트 — 포인트/메시지/인프런/글쓰기 참여                   | 각 라우터별 파일               |
| 7    | 슬랙 핸들러 테스트 — core, contents                             | `test/slack/test_*.py`         |
| 8    | 슬랙 핸들러 테스트 — community(커피챗), subscriptions           | 〃                             |
| 9    | 슬랙 핸들러 테스트 — log(reaction), writing_participation       | 〃                             |
| 10   | 미들웨어 테스트 (`log_event_middleware`, `dependency_injection_middleware`, `handle_error`) | `test/slack/test_event_handler_middlewares.py` |
| 11   | 통합/회귀: 기존 `test_point.py`, `test_reminder.py` 정리         | 디렉터리 이동                 |

각 단계는 `uv run pytest test/...`로 검증 후 다음 단계로 넘어간다.

---

## 5. 테스트 작성 가이드라인

- **AAA 패턴**: `# given` `# when` `# then`. 한국어 주석 OK (기존 스타일과 동일).
- **하나의 테스트 = 하나의 시나리오**. 케이스가 많으면 `@pytest.mark.parametrize`.
- **외부 의존성은 항상 mock**. 단, JWT/직렬화/도메인 모델 같은 순수 함수는 실제 호출.
- **CSV 의존 함수**는 `tmp_path` + `monkeypatch.chdir(tmp_path)` 후 헬퍼로 픽스처 csv 생성.
- **시간 의존 함수**는 `mocker.patch("app.utils.tz_now", ...)`처럼 명확하게 고정.
- **에러 메시지 검증**은 한국어 본문 일부를 `in`으로 비교(완전일치는 깨지기 쉬움).
- **응답 검증**은 status_code + 본문 핵심 필드 두 가지를 함께.

---

## 6. 비기능적 정리 (별도 작업 권장)

이 문서가 아닌, 테스트 보강 후 별도 작업으로 분리하면 좋은 항목들이다.

- `app/api/views/contents.py` 의 `/contents` 라우터에서 매 요청마다 CSV를 `pl.read_csv`하는 부분 캐싱
- `SlackRepository`의 CSV 매번 read 패턴 → 인메모리 인덱스 또는 DB 이전
- `app/__init__.py`의 OnEvent("startup") 안 헬퍼들이 모듈 스코프에서 정의되는 구조 정리
- `requests` 동기 호출 → `httpx.AsyncClient`로 통일 (community.py 의 ephemeral 삭제 부분)

이 단계들은 본 작업 범위 밖이며, 테스트가 충분히 갖춰진 다음 자유롭게 시도하면 된다.
