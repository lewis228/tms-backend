#!/usr/bin/env bash
#
# reset_db.sh — TMS 로컬 DB 완전 초기화 + 시드 (한 방 복구)
#
#   기본:        docker 볼륨까지 날리고 → 인프라 재기동 → 스키마 생성 → 시드
#   --seed-only: docker 는 그대로 두고 → 스키마(upgrade head) → 시드만
#
# 사용:
#   ./scripts/reset_db.sh              # 풀 리셋 (볼륨 삭제 포함, 파괴적)
#   ./scripts/reset_db.sh --seed-only  # 떠있는 DB 에 마이그레이션+시드만
#
# 로그인: test@test.com / 1234  (role=ADMIN)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

COMPOSE_FILE="docker-compose.local.yaml"
MYSQL_CONTAINER="tms-mysql"
WIPE_DOCKER=1

for arg in "$@"; do
  case "$arg" in
    --seed-only|--no-docker) WIPE_DOCKER=0 ;;
    -h|--help)
      awk 'NR>1 && /^#/ {sub(/^# ?/,""); print; next} NR>1 {exit}' "${BASH_SOURCE[0]}"
      exit 0 ;;
    *) echo "알 수 없는 옵션: $arg (사용법: --help)"; exit 1 ;;
  esac
done

# ── venv 활성화 ──────────────────────────────────────────────
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [ -f venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
else
  echo "⚠️  venv 를 찾지 못했습니다 (.venv / venv). 시스템 python 으로 진행합니다."
fi

step() { echo; echo "▶ $*"; }

if [ "$WIPE_DOCKER" -eq 1 ]; then
  step "[1/5] docker compose down -v  (tms 컨테이너 + 볼륨 삭제)"
  docker compose -f "$COMPOSE_FILE" down -v

  step "[2/5] docker compose up -d  (인프라: mysql/redis/minio)"
  docker compose -f "$COMPOSE_FILE" up -d mysql redis minio minio-init

  step "[3/5] mysql healthy 대기 …"
  for i in $(seq 1 90); do
    status="$(docker inspect --format '{{.State.Health.Status}}' "$MYSQL_CONTAINER" 2>/dev/null || echo starting)"
    if [ "$status" = "healthy" ]; then
      echo "   ✅ $MYSQL_CONTAINER healthy (~$((i * 2))s)"
      break
    fi
    if [ "$i" -eq 90 ]; then
      echo "   ❌ mysql 이 제한 시간 내 healthy 되지 않았습니다."; exit 1
    fi
    sleep 2
  done
else
  step "[skip] docker (--seed-only) — 떠있는 DB 사용"
fi

step "[4/5] alembic upgrade head  (스키마 생성/최신화)"
alembic upgrade head

step "[5/5] scripts/seed.py  (전 테이블 시드)"
PYTHONPATH=src python scripts/seed.py

echo
echo "✅ 완료 — 로그인: test@test.com / 1234"
