# database/event_hooks.py
"""
SQLAlchemy 이벤트 훅 (디버깅용)
(write_engine 사용으로 변경)
"""
from common.const.settings import settings


# ===== 디버깅용 이벤트 훅 (개발 환경에서만 활성화) =====
if settings.ENV == "development":
    
    # Write Engine 이벤트
    # @event.listens_for(write_engine.sync_engine, "begin")
    # def before_write_transaction_begin(conn):
    #     print("🔥 [WRITE 트랜잭션 시작] conn:", conn)

    # @event.listens_for(write_engine.sync_engine, "commit")
    # def before_write_transaction_commit(conn):
    #     print("✅ [WRITE 트랜잭션 커밋] conn:", conn)

    # @event.listens_for(write_engine.sync_engine, "rollback")
    # def before_write_transaction_rollback(conn):
    #     print("❌ [WRITE 트랜잭션 롤백] conn:", conn)

    # Read Engine 이벤트 (read_engine != write_engine인 경우만)
    # if read_engine is not write_engine:
    #     @event.listens_for(read_engine.sync_engine, "begin")
    #     def before_read_transaction_begin(conn):
    #         print("📖 [READ 트랜잭션 시작] conn:", conn)
    
    pass