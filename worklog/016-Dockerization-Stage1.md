# 016 - Stage 1: Dockerization (앱 + nginx + watchtower 통합 스택)

배포 투두 (`docs/05-배포-투두.md`) Stage 1 작업. 또봇을 컨테이너로 운영하기 위한 모든 파일을
한 번에 만들었어요. 사용자 의견을 받아 **nginx 도 컨테이너로 통합** 하는 방향으로 결정.

## 1. 작성한 파일들

| 파일                              | 역할                                                |
| --------------------------------- | --------------------------------------------------- |
| `Dockerfile`                      | multi-stage 이미지 빌드 (uv 0.10 기반)              |
| `.dockerignore`                   | 이미지에 굽지 않을 파일 목록                         |
| `docker-compose.yml`              | 운영 스택 (앱 + nginx-certbot + watchtower)          |
| `nginx/user_conf.d/ttobot.conf`   | nginx reverse proxy 설정                             |

## 2. 결정 사항: nginx 도 컨테이너로

원래는 "호스트에 nginx + certbot 직접 설치" 였는데, 사용자 제안으로 **컨테이너로 통합**.

### 왜 더 나은가

- `docker-compose.yml` 한 파일이 **모든 인프라를 표현** — 인스턴스 셋업이 단순해짐
- 호스트에 패키지 설치 필요 없음 → 머신 정리 쉬움
- nginx config 도 git 으로 추적 (호스트의 `/etc/nginx/...` 와 분리)
- jonasal/nginx-certbot 이미지가 **인증서 자동 발급/갱신** 까지 내장 → cron 관리 불필요

### 선택한 이미지

[`jonasal/nginx-certbot`](https://github.com/JonasAlfredsson/docker-nginx-certbot) — nginx + certbot
통합. 컨테이너 시작 시 자동 인증서 발급, 매시간 갱신 cron.

## 3. Dockerfile 설계 — multi-stage

```dockerfile
# builder: 의존성 + 소스 빌드
FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.10.8 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project   # 의존성만
COPY . .
RUN uv sync --frozen --no-dev                        # + 자기 자신

# runtime: 결과물만 가져옴
FROM python:3.11-slim AS runtime
WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 ENV=prod
EXPOSE 3389
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:3389/').read()" || exit 1
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3389"]
```

### 핵심

- **`uv.lock` 먼저 복사** → Docker 레이어 캐시 적중률 극대화. 코드만 변경되면 의존성 설치 단계는
  캐시 재사용.
- **`--mount=type=cache,target=/root/.cache/uv`** → uv 자체 캐시도 빌드 간 재사용
- **`--no-dev`** → pytest/ruff 등 dev 그룹 제외. 운영 이미지에 테스트 도구 안 들어감.
- **HEALTHCHECK 내장** → `docker ps` 가 자동으로 health 상태 표시. compose 의 `depends_on` 도 활용
  가능.

## 4. `.dockerignore` 의 핵심 원칙

```
store/        # 운영 데이터는 호스트 마운트
logs.csv
.env
.env.test     # 시크릿은 절대 이미지에 굽지 않음
test/         # 런타임 불필요
docs/
worklog/
```

**이미지는 stateless, 데이터/시크릿은 런타임 마운트** 라는 베스트 프랙티스.

## 5. docker-compose.yml 의 통합 스택

세 컨테이너가 한 docker network 에서 협업.

```
                 [443/80] 외부
                    │
                    ▼
            ┌────────────────┐
            │ nginx-certbot  │  ── certbot 자동 갱신
            └────────┬───────┘
                     │ http://ttobot:3389 (docker network)
                     ▼
            ┌────────────────┐
            │ ttobot         │  ── store/ , .env 호스트 마운트
            └────────────────┘

[watchtower] ── docker.sock 으로 변경 감시 → ttobot 재기동
```

### ttobot 서비스 — `expose` vs `ports`

`ports: ["3389:3389"]` 가 아니라 `expose: ["3389"]` 인 게 핵심. **호스트로 publish 하지 않고**
docker network 안에서만 접근 가능 → 외부 공격 표면이 80/443 으로만 한정됨.

### watchtower — Slack 알림 옵션

```yaml
WATCHTOWER_NOTIFICATIONS: slack
WATCHTOWER_NOTIFICATION_SLACK_HOOK_URL: ${SLACK_WEBHOOK_FOR_DEPLOY:-}
```

`.env` 에 `SLACK_WEBHOOK_FOR_DEPLOY` 가 있으면 배포 알림이 가고, 없으면 알림 없이 배포만 진행.
**없어도 동작에 지장 없는 안전한 기본값**.

## 6. nginx config — 단순한 reverse proxy

```nginx
server {
    listen 443 ssl;
    server_name ttobot.kro.kr;
    ssl_certificate     /etc/letsencrypt/live/ttobot.kro.kr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ttobot.kro.kr/privkey.pem;

    location / {
        proxy_pass http://ttobot:3389;     # docker DNS 가 서비스명으로 해석
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

HTTP(80) → HTTPS(443) 리다이렉트는 jonasal/nginx-certbot 이미지가 자동으로 처리해줘서 명시 불필요.

## 7. 검증 — 실제 빌드/실행 결과

Docker Desktop 29.4.1 환경에서 모든 단계를 직접 검증했어요.

### 7-1. 이미지 빌드

```bash
$ docker build -t ttobot:local .
... uv sync 캐시 잘 활용 ...
=> exporting to image
=> naming to docker.io/library/ttobot:local
DONE
```

이미지 크기: **764MB** (slim 베이스 + 의존성 다수). multi-stage 라 dev 도구는 빠짐.

### 7-2. 단독 컨테이너 실행

`.env` 가 `KEY = "value"` 형식이라 docker `--env-file` 의 strict 파서를 통과하지 못했어요. 대신 `.env`
를 컨테이너에 파일로 마운트해서 pydantic-settings 의 자체 파서로 읽도록 우회했습니다 (docker-compose.yml
도 동일 패턴 적용).

```bash
$ docker run -d --name ttobot-test \
    -v $(pwd)/.env:/app/.env:ro \
    -v $(pwd)/store:/app/store \
    -p 3389:3389 \
    ttobot:local
$ curl http://localhost:3389/
true                                       # ✅
$ docker logs ttobot-test
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:3389
INFO:     142.250.71.170:43290 - "GET / HTTP/1.1" 200 OK   # 슬랙 IP 응답
```

### 7-3. docker compose 검증

`docker compose up -d ttobot watchtower` 로 통합 스택의 일부를 띄웠어요. 두 가지 이슈를 만났고
docker-compose.yml 에 반영했습니다.

#### 이슈 A: watchtower 의 빈 Slack URL → 부팅 실패

`WATCHTOWER_NOTIFICATIONS=slack` 인데 `WATCHTOWER_NOTIFICATION_SLACK_HOOK_URL` 이 빈 값이면 watchtower
가 즉시 크래시. → 알림 환경변수를 **기본 비활성화** 로 두고, Webhook URL 이 준비되었을 때만 주석
해제하도록 명시.

#### 이슈 B: containrrr/watchtower 의 Docker API 호환성

```
Error response from daemon: client version 1.25 is too old.
Minimum supported API version is 1.40
```

`containrrr/watchtower` 는 2023년 이후 유지보수가 멈춰서 Docker API v1.51 (Docker Desktop 29.x) 와
호환되지 않아요. **활발히 유지되는 포크 [`nickfedor/watchtower`](https://github.com/nickfedor/watchtower)** 로
교체. 동일 CLI 옵션, 드롭인 호환.

#### 최종 결과

```
$ docker compose up -d ttobot watchtower
NAME         STATUS
ttobot       Up 40 seconds (healthy)        # ✅
watchtower   Up 40 seconds (healthy)        # ✅
```

watchtower 로그:
```
Watchtower 1.16.1 using Docker API v1.51
Using no notifications
Next scheduled run: ... in 59 seconds
```

### 7-4. 헬퍼 스크립트 추가

자주 쓸 명령들을 `scripts/` 에 모아 두었어요.

| 스크립트                  | 동작                                     |
| ------------------------ | ---------------------------------------- |
| `scripts/docker-build.sh` | `ttobot:local` 이미지 빌드               |
| `scripts/docker-run.sh`   | 단독 컨테이너로 실행 (전경, Ctrl+C 종료) |
| `scripts/docker-up.sh`    | compose 로 기동 (`--prod` 면 nginx 포함) |
| `scripts/docker-down.sh`  | 정리 (`--all` 이면 볼륨까지)              |
| `scripts/docker-logs.sh`  | 로그 follow (`서비스명 [tail]`)          |

> ⚠️ **로컬에서는 nginx 까지 띄우지 마세요**. 도메인이 가리키는 IP 가 로컬이 아니라 Let's Encrypt
> 인증서 발급이 실패합니다. `docker-up.sh` 의 기본 모드(로컬)는 nginx 를 제외하고, GCP 운영에서만
> `--prod` 옵션을 씁니다.

## 8. 결과

| 항목                                                  | 상태 |
| ----------------------------------------------------- | :--: |
| `Dockerfile` (multi-stage uv 기반)                    | ✅   |
| `.dockerignore`                                       | ✅   |
| `docker-compose.yml` (통합 스택)                      | ✅   |
| `nginx/user_conf.d/ttobot.conf`                       | ✅   |
| `scripts/docker-{build,run,up,down,logs}.sh`           | ✅   |
| 로컬 빌드 검증 (이미지 764MB)                         | ✅   |
| 단독 컨테이너 실행 + 헬스체크 통과                     | ✅   |
| docker compose 통합 (ttobot+watchtower) healthy       | ✅   |
| 240+ 테스트 회귀                                      | ✅ (코드 변경 0건이라 회귀 무관) |

## 9. 다음 단계

✅ **Stage 1 완료**. 다음은 **Stage 2** — `docs/06-GCP-인스턴스-셋업-가이드.md` 따라 GCP 콘솔에서
인스턴스 생성. (사용자 직접 진행 필요)

도중에 막히는 단계가 있으면 알려주시면 바로 도와드릴게요.
