"""File Repository."""
from __future__ import annotations

from app.core.repository import BaseRepository
from app.domains.files.models import File


class FileRepository(BaseRepository[File]):
    model = File

    async def list_by_attach(self, domain: str, object_id: str) -> list[File]:
        stmt = self._base_query().where(
            File.domain == domain, File.object_id == object_id
        ).order_by(File.created_at)
        return list((await self.db.execute(stmt)).scalars().all())
