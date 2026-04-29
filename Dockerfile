# syntax=docker/dockerfile:1.7

# ---- builder stage: 의존성 설치 + 소스 동기화 ----
FROM python:3.11-slim AS builder

# uv 바이너리만 복사 (이미지 슬림 유지)
COPY --from=ghcr.io/astral-sh/uv:0.10.8 /uv /uvx /bin/

WORKDIR /app

# 의존성 lock 파일만 먼저 복사해서 캐시 적중률 최대화
COPY pyproject.toml uv.lock ./

# 의존성 설치 (lock 기반, dev 그룹 제외, 자기 자신은 아직 설치 X)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# 소스 복사 후 자기 자신까지 설치
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# ---- runtime stage: 런타임에 필요한 것만 ----
FROM python:3.11-slim AS runtime

WORKDIR /app

# 빌더 stage 에서 만든 .venv 와 소스 트리만 복사
COPY --from=builder /app /app

# .venv/bin 을 PATH 에 추가해서 uvicorn / python 직접 호출 가능
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    ENV=prod

EXPOSE 3389

# 헬스체크: GET / 가 200 응답 (FastAPI health endpoint)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:3389/').read()" || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3389"]
