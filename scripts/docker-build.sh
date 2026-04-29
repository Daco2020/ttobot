#!/usr/bin/env bash
# 또봇 Docker 이미지를 로컬에 빌드한다.
# 사용: ./scripts/docker-build.sh

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)

cd "$ROOT_DIR"

echo "🔨 ttobot:local 이미지 빌드 중..."
docker build -t ttobot:local .

echo "✅ 빌드 완료. 이미지 정보:"
docker images ttobot:local --format "  {{.Repository}}:{{.Tag}} ({{.Size}})"
