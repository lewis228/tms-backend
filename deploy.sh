#!/usr/bin/env bash
#
# deploy.sh — TMS 운영 배포 (단일 서버, 1GB RAM).
#
#   ./deploy.sh           # 빌드(순차) → 기동 → 마이그레이션
#   ./deploy.sh --seed    # 위 + 데모 시드(test@test.com / 1234, 전 테이블 초기화)
#   ./deploy.sh --no-build # 빌드 생략(코드 변경 없이 재기동)
#
# 전제:
#   - 이 디렉토리(tms-backend)와 ../tms-frontend 가 형제로 존재
#   - .env.prod 작성 완료 (cp .env.prod.example .env.prod 후 시크릿 채움)
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

COMPOSE="docker compose --env-file .env.prod -f docker-compose.prod.yaml"
SEED=0
BUILD=1
for arg in "$@"; do
  case "$arg" in
    --seed) SEED=1 ;;
    --no-build) BUILD=0 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "알 수 없는 옵션: $arg"; exit 1 ;;
  esac
done

if [ ! -f .env.prod ]; then
  echo "❌ .env.prod 없음. 먼저: cp .env.prod.example .env.prod 후 시크릿을 채우세요."
  exit 1
fi
if [ ! -d ../tms-frontend ]; then
  echo "❌ ../tms-frontend 없음. tms-backend 와 tms-frontend 를 형제로 clone 하세요."
  exit 1
fi

step() { echo; echo "▶ $*"; }

if [ "$BUILD" -eq 1 ]; then
  # 1GB RAM → 병렬 빌드 OOM 방지: 백엔드 먼저, 그다음 무거운 프론트 단독 빌드
  step "[1/4] 백엔드 이미지 빌드"
  $COMPOSE build app
  step "[2/4] 프론트 이미지 빌드 (Vite, 단독)"
  $COMPOSE build web
fi

step "[3/4] 컨테이너 기동"
$COMPOSE up -d

step "    app healthy 대기 …"
for i in $(seq 1 40); do
  status="$(docker inspect --format '{{.State.Health.Status}}' tms-api 2>/dev/null || echo starting)"
  [ "$status" = "healthy" ] && { echo "   ✅ app healthy (~$((i * 5))s)"; break; }
  [ "$i" -eq 40 ] && { echo "   ⚠️ app healthy 지연 — 로그 확인: $COMPOSE logs app"; }
  sleep 5
done

step "[4/4] DB 마이그레이션 (alembic upgrade head)"
$COMPOSE exec -T app alembic upgrade head

if [ "$SEED" -eq 1 ]; then
  step "[+] 데모 시드 (전 테이블 초기화 + test@test.com/1234)"
  $COMPOSE exec -T app sh -c "PYTHONPATH=src python scripts/seed.py"
fi

echo
echo "✅ 배포 완료 — http://168.107.40.234 접속"
$COMPOSE ps
