#!/usr/bin/env bash
# docker compose 스택을 정리한다 (컨테이너/네트워크 삭제).
# - 볼륨(nginx_secrets)은 기본적으로 보존.
# - 사용:
#     ./scripts/docker-down.sh         # 컨테이너만 정리
#     ./scripts/docker-down.sh --all   # 볼륨까지 삭제 (인증서 재발급 필요)

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)

cd "$ROOT_DIR"

if [ "${1:-}" = "--all" ]; then
    echo "🧹 컨테이너 + 볼륨 정리 (인증서 포함 모두 삭제)"
    docker compose down -v
else
    echo "🛑 컨테이너 정리 (볼륨은 유지)"
    docker compose down
fi
