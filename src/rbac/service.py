from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from rbac.repository import RbacRepository


class RbacService:
    def __init__(self, db: AsyncSession):
        self.db = db
