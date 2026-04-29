#!/usr/bin/env bash
# docker compose 로 통합 스택을 띄운다.
# - 로컬 (기본): ttobot + watchtower 만 (nginx 제외, 도메인 없으니 인증서 발급 실패함).
# - 운영(GCP 인스턴스)에서는 `--prod` 옵션으로 nginx 까지 포함.
#
# 사용:
#   ./scripts/docker-up.sh           # 로컬 (ttobot + watchtower)
#   ./scripts/docker-up.sh --prod    # 운영 (전체 스택)

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)

cd "$ROOT_DIR"

MODE="local"
if [ "${1:-}" = "--prod" ]; then
    MODE="prod"
fi

if [ "$MODE" = "prod" ]; then
    echo "🚀 운영 스택 기동 (ttobot + nginx + watchtower)"
    docker compose up -d
else
    echo "🚀 로컬 스택 기동 (ttobot + watchtower; nginx 제외)"
    docker compose up -d ttobot watchtower
fi

echo ""
echo "📋 컨테이너 상태:"
docker compose ps

echo ""
echo "📜 로그를 보려면: ./scripts/docker-logs.sh"
echo "🛑 중단하려면:   ./scripts/docker-down.sh"
