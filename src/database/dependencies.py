# database/dependencies.py
"""
데이터베이스 의존성 (K8s 읽기/쓰기 분리 지원)

사용법:
  - SELECT: Depends(get_read_db) 또는 Depends(get_db)
  - INSERT/UPDATE/DELETE: Depends(get_write_db)

개발 환경에서는 둘 다 같은 DB를 사용하므로 동작에 차이 없음.
운영 환경에서는 읽기는 Replica로 분산, 쓰기는 Primary로 집중.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from database.mysql_connection import write_session_maker, read_session_maker


async def get_write_db() -> AsyncGenerator[AsyncSession, None]:
    """
    쓰기용 세션 (Primary)
    
    사용 시점:
      - INSERT, UPDATE, DELETE
      - 트랜잭션이 필요한 경우
      - 즉시 일관성이 필요한 경우
    """
    async with write_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    """
    읽기용 세션 (Replica로 분산)
    
    사용 시점:
      - SELECT (단순 조회)
      - 리스트 조회, 검색
      - 통계/분석 쿼리
    
    주의:
      - Replication Lag으로 인해 방금 쓴 데이터가 안 보일 수 있음
      - 즉시 일관성이 필요하면 get_write_db 사용
    """
    async with read_session_maker() as session:
        try:
            yield session
        finally:
            # 읽기 전용이므로 commit 불필요
            pass


# ===== 레거시 호환 =====
# 기존 코드에서 get_db를 사용하는 경우
# 기본적으로 쓰기 세션 반환 (안전한 기본값)
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    레거시 호환용 세션 (쓰기 세션)
    
    새 코드에서는 명시적으로 get_write_db 또는 get_read_db 사용 권장.
    """
    async with write_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise