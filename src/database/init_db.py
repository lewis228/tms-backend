from common.model.models_registry import Base
from database.mysql_connection import write_engine


async def init_db():
    async with write_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
