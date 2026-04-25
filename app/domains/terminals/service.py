"""Terminal 서비스."""
from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.domains.terminals.models import Terminal
from app.domains.terminals.repository import TerminalRepository
from app.domains.terminals.schema import TerminalCreateRequest, TerminalUpdateRequest


class TerminalService:
    def __init__(self, repo: TerminalRepository, tenant_id: str) -> None:
        self.repo = repo
        self.tenant_id = tenant_id

    async def create(self, payload: TerminalCreateRequest) -> Terminal:
        t = Terminal(tenant_id=self.tenant_id, **payload.model_dump())
        await self.repo.create(t)
        await self.repo.db.commit()
        await self.repo.db.refresh(t)
        return t

    async def get(self, id_: str) -> Terminal:
        t = await self.repo.get_by_id(id_)
        if not t:
            raise NotFoundError("Terminal not found")
        return t

    async def list_paged(self, params):
        return await self.repo.list_paged(params)

    async def update(self, id_: str, payload: TerminalUpdateRequest) -> Terminal:
        t = await self.get(id_)
        await self.repo.update(t, **payload.model_dump(exclude_unset=True))
        await self.repo.db.commit()
        await self.repo.db.refresh(t)
        return t

    async def delete(self, id_: str) -> None:
        t = await self.get(id_)
        await self.repo.soft_delete(t)
        await self.repo.db.commit()
