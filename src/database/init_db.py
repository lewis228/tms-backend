# database/init_db.py
"""
데이터베이스 초기화
(write_engine 사용으로 변경)
"""
from common.model.models_registry import Base
from database.mysql_connection import write_engine


async def init_db():
    """
    데이터베이스 테이블 생성
    
    DDL은 항상 Primary(write_engine)에서 실행해야 함.
    """
    async with write_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)