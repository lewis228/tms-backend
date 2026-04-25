#!/usr/bin/env bash
set -e

export PYTHONPATH=/app/src

# 환경변수는 Python 부트스트랩(src/common/const/config_bootstrap.py)이
# .env 또는 AWS Parameter Store에서 로드한다. 여기서는 검사를 하지 않는다.

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

echo "[entrypoint] seed test accounts"
PYTHONPATH=/app/src python /app/scripts/seed_test_user.py

echo "[entrypoint] start uvicorn on :8080"
exec uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1 --app-dir /app/src
