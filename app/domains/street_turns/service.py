"""StreetTurn 서비스 — 사전 조건 검증.

조건:
- Import D/O = COMPLETED
- Export D/O = DISPATCHED
- 두 D/O 의 container_number 동일 (둘 다 not null)
- Import / Export 둘 다 기존 StreetTurn 이 없어야 함
"""
from __future__ import annotations

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.delivery_orders.repository import DeliveryOrderRepository
from app.domains.street_turns.models import StreetTurn
from app.domains.street_turns.repository import StreetTurnRepository
from app.domains.street_turns.schema import StreetTurnCreateRequest
from app.models.enums import DeliveryStatus, ShipmentDirection


class StreetTurnService:
    def __init__(
        self,
        repo: StreetTurnRepository,
        do_repo: DeliveryOrderRepository,
        tenant_id: str,
    ) -> None:
        self.repo = repo
        self.do_repo = do_repo
        self.tenant_id = tenant_id

    async def create(self, payload: StreetTurnCreateRequest) -> StreetTurn:
        imp = await self.do_repo.get_by_id(payload.import_order_id)
        exp = await self.do_repo.get_by_id(payload.export_order_id)
        if not imp:
            raise NotFoundError("Import D/O not found")
        if not exp:
            raise NotFoundError("Export D/O not found")
        if imp.direction != ShipmentDirection.IMPORT:
            raise ValidationError("import_order_id must reference an IMPORT D/O")
        if exp.direction != ShipmentDirection.EXPORT:
            raise ValidationError("export_order_id must reference an EXPORT D/O")
        if imp.status != DeliveryStatus.COMPLETED:
            raise ValidationError("Import D/O must be COMPLETED")
        if exp.status != DeliveryStatus.DISPATCHED:
            raise ValidationError("Export D/O must be DISPATCHED")
        if not imp.container_number or imp.container_number != exp.container_number:
            raise ValidationError("Import and Export must share container_number")
        if await self.repo.find_by_order(imp.id):
            raise ConflictError("Import D/O already linked to a StreetTurn")
        if await self.repo.find_by_order(exp.id):
            raise ConflictError("Export D/O already linked to a StreetTurn")
        st = StreetTurn(
            tenant_id=self.tenant_id,
            import_order_id=imp.id,
            export_order_id=exp.id,
            container_number=imp.container_number,
            link_type=payload.link_type,
            note=payload.note,
        )
        await self.repo.create(st)
        await self.repo.db.commit()
        await self.repo.db.refresh(st)
        return st

    async def get(self, id_: str) -> StreetTurn:
        st = await self.repo.get_by_id(id_)
        if not st:
            raise NotFoundError("StreetTurn not found")
        return st

    async def list_paged(self, params):
        return await self.repo.list_paged(params)

    async def delete(self, id_: str) -> None:
        st = await self.get(id_)
        await self.repo.soft_delete(st)
        await self.repo.db.commit()
