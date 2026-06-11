# tests/conftest.py
"""pytest 전역 설정.

- PYTHONPATH=src 주입 (sys.path 보정)
- asyncio_mode=auto (pyproject 에서도 설정)
- 통합 테스트는 tests/integration/conftest.py 가 별도 fixture 제공

⚠️ 테스트는 항상 전용 DB(tms_test)를 쓴다 — dev DB(tms) 의 시드 데이터를
   TRUNCATE 로 날리던 문제의 근본 해결. pydantic Settings 는 env var 가
   .env 파일보다 우선하므로, settings 모듈이 import 되기 전(이 파일이
   가장 먼저 실행됨)에 DB_DATABASE 를 강제 덮어쓴다.
   tms_test 생성/마이그레이션은 tests/integration/conftest.py 의
   세션 픽스처(_prepare_test_db)가 자동 수행.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# src 를 sys.path 에 보정 (pytest 실행 시 PYTHONPATH 설정 안 해도 동작)
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault("PYTHONUNBUFFERED", "1")
# 테스트 프로세스는 무조건 전용 DB — setdefault 가 아니라 강제(셸 env 로 우회 불가)
os.environ["DB_DATABASE"] = "tms_test"
