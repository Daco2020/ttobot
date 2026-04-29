#!/usr/bin/env bash
# docker compose 의 로그를 본다.
# 사용:
#   ./scripts/docker-logs.sh              # 모든 서비스, follow 모드
#   ./scripts/docker-logs.sh ttobot        # 특정 서비스만
#   ./scripts/docker-logs.sh ttobot 100    # 마지막 100줄부터 follow

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)

cd "$ROOT_DIR"

SERVICE="${1:-}"
TAIL="${2:-50}"

if [ -z "$SERVICE" ]; then
    docker compose logs -f --tail="$TAIL"
else
    docker compose logs -f --tail="$TAIL" "$SERVICE"
fi
