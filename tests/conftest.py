# tests/conftest.py
"""pytest 전역 설정.

- PYTHONPATH=src 주입 (sys.path 보정)
- asyncio_mode=auto (pyproject 에서도 설정)
- 통합 테스트는 tests/integration/conftest.py 가 별도 fixture 제공
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

# 테스트용 .env 가 별도 있으면 로드, 아니면 기본 .env 사용
os.environ.setdefault("PYTHONUNBUFFERED", "1")
