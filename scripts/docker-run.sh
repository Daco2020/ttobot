#!/usr/bin/env bash
# 빌드된 ttobot:local 이미지를 단독 컨테이너로 실행한다 (앱만 / nginx X / watchtower X).
# 사용: ./scripts/docker-run.sh
# 종료: Ctrl+C 또는 다른 터미널에서 `docker stop ttobot-test`

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)

cd "$ROOT_DIR"

if ! docker image inspect ttobot:local >/dev/null 2>&1; then
    echo "⚠️  ttobot:local 이미지가 없어요. 먼저 ./scripts/docker-build.sh 를 실행해주세요."
    exit 1
fi

# 이전에 띄웠던 컨테이너가 남아있으면 정리.
docker rm -f ttobot-test >/dev/null 2>&1 || true

echo "🚀 ttobot-test 컨테이너 실행 (호스트 :3389 → 컨테이너 :3389)"
echo "   curl http://localhost:3389/ 로 헬스체크 확인 가능"
echo "   Ctrl+C 로 종료"
echo ""

docker run --rm -it \
    --name ttobot-test \
    -v "$ROOT_DIR/.env:/app/.env:ro" \
    -v "$ROOT_DIR/store:/app/store" \
    -p 3389:3389 \
    ttobot:local
