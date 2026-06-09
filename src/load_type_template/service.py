# src/load_type_template/service.py
from __future__ import annotations
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, ConflictException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from load_type_template.repository import LoadTypeTemplateRepository
from load_type_template.schemas.request import (
    LoadTypeTemplateCreateRequest, LoadTypeTemplateUpdateRequest,
    PaginateLoadTypeTemplateRequest, TemplateStepsReplaceRequest,
)
from load_type_template.schemas.response import (
    LoadTypeTemplateResponseSchema, LoadTypeTemplateSummarySchema,
    LoadTypeTemplateDeleteResponseSchema, SeedDefaultsResponseSchema,
)
from load_type_template.const.status import (
    LoadDirection as D, TemplateLocationType as L, TemplateMoveType as M,
    TemplateServiceType as S, TemplateMoveCode as MC,
)

_LABEL = "Load Type Template"


def _step(seq, frm, to, move, svc, code=None, flags=None):
    return {"seq": seq, "from_location_type": frm, "to_location_type": to,
            "move_type": move, "service_type": svc, "move_code": code, "flags": flags, "note": None}


# 컨플루언스 "Load Type 템플릿" 16종 (Leg 유형 분석)
_DEFAULTS = [
    ("IMP_DIRECT_L", "Import Direct (Live)", D.IMPORT, [
        _step(1, L.TERMINAL, L.CUSTOMER, M.LOAD, S.LIVE, MC.PPU),
        _step(2, L.CUSTOMER, L.TERMINAL, M.EMPTY, S.LIVE, MC.PRE)]),
    ("IMP_DIRECT_D", "Import Direct (Drop)", D.IMPORT, [
        _step(1, L.TERMINAL, L.CUSTOMER, M.LOAD, S.DROP, MC.PPU),
        _step(2, L.CUSTOMER, L.TERMINAL, M.EMPTY, S.LIVE, MC.PRE)]),
    ("IMP_PRE_L", "Import Pre-pull (Live)", D.IMPORT, [
        _step(1, L.TERMINAL, L.YARD, M.LOAD, S.DROP, MC.PPL),
        _step(2, L.YARD, L.CUSTOMER, M.LOAD, S.LIVE),
        _step(3, L.CUSTOMER, L.TERMINAL, M.EMPTY, S.LIVE, MC.PRE)]),
    ("IMP_PRE_D", "Import Pre-pull (Drop)", D.IMPORT, [
        _step(1, L.TERMINAL, L.YARD, M.LOAD, S.DROP, MC.PPL),
        _step(2, L.YARD, L.CUSTOMER, M.LOAD, S.DROP),
        _step(3, L.CUSTOMER, L.TERMINAL, M.EMPTY, S.LIVE, MC.PRE)]),
    ("IMP_POST_L", "Import Post-yard (Live)", D.IMPORT, [
        _step(1, L.TERMINAL, L.CUSTOMER, M.LOAD, S.LIVE, MC.PPU),
        _step(2, L.CUSTOMER, L.YARD, M.EMPTY, S.DROP),
        _step(3, L.YARD, L.TERMINAL, M.EMPTY, S.LIVE, MC.PRE)]),
    ("IMP_POST_D", "Import Post-yard (Drop)", D.IMPORT, [
        _step(1, L.TERMINAL, L.CUSTOMER, M.LOAD, S.DROP, MC.PPU),
        _step(2, L.CUSTOMER, L.YARD, M.EMPTY, S.DROP),
        _step(3, L.YARD, L.TERMINAL, M.EMPTY, S.LIVE, MC.PRE)]),
    ("IMP_FULL_L", "Import Full Yard (Live)", D.IMPORT, [
        _step(1, L.TERMINAL, L.YARD, M.LOAD, S.DROP, MC.PPL),
        _step(2, L.YARD, L.CUSTOMER, M.LOAD, S.LIVE),
        _step(3, L.CUSTOMER, L.YARD, M.EMPTY, S.DROP),
        _step(4, L.YARD, L.TERMINAL, M.EMPTY, S.LIVE, MC.PRE)]),
    ("IMP_FULL_L_CS", "Import Full Yard (Live) + Chassis Split", D.IMPORT, [
        _step(1, L.YARD, L.TERMINAL, M.NONE, S.NONE, None, {"chassis_split": True}),
        _step(2, L.TERMINAL, L.YARD, M.LOAD, S.DROP, MC.PPL),
        _step(3, L.YARD, L.CUSTOMER, M.LOAD, S.LIVE),
        _step(4, L.CUSTOMER, L.YARD, M.EMPTY, S.DROP),
        _step(5, L.YARD, L.TERMINAL, M.EMPTY, S.LIVE, MC.PRE)]),
    ("IMP_FULL_D", "Import Full Yard (Drop)", D.IMPORT, [
        _step(1, L.TERMINAL, L.YARD, M.LOAD, S.DROP, MC.PPL),
        _step(2, L.YARD, L.CUSTOMER, M.LOAD, S.DROP),
        _step(3, L.CUSTOMER, L.YARD, M.EMPTY, S.DROP),
        _step(4, L.YARD, L.TERMINAL, M.EMPTY, S.LIVE, MC.PRE)]),
    ("IMP_REPOSITION", "Import Reposition", D.IMPORT, [
        _step(1, L.TERMINAL, L.TERMINAL, M.EMPTY, S.LIVE, MC.ERP)]),
    ("EXP_DIRECT_L", "Export Direct (Live)", D.EXPORT, [
        _step(1, L.TERMINAL, L.CUSTOMER, M.EMPTY, S.LIVE),
        _step(2, L.CUSTOMER, L.TERMINAL, M.LOAD, S.LIVE)]),
    ("EXP_DIRECT_D", "Export Direct (Drop)", D.EXPORT, [
        _step(1, L.TERMINAL, L.CUSTOMER, M.EMPTY, S.DROP),
        _step(2, L.CUSTOMER, L.TERMINAL, M.LOAD, S.LIVE)]),
    ("EXP_PRE_L", "Export Pre-pull (Live)", D.EXPORT, [
        _step(1, L.TERMINAL, L.YARD, M.EMPTY, S.DROP, MC.PPL),
        _step(2, L.YARD, L.CUSTOMER, M.EMPTY, S.LIVE),
        _step(3, L.CUSTOMER, L.TERMINAL, M.LOAD, S.LIVE)]),
    ("EXP_PRE_D", "Export Pre-pull (Drop)", D.EXPORT, [
        _step(1, L.TERMINAL, L.YARD, M.EMPTY, S.DROP, MC.PPL),
        _step(2, L.YARD, L.CUSTOMER, M.EMPTY, S.DROP),
        _step(3, L.CUSTOMER, L.TERMINAL, M.LOAD, S.LIVE)]),
    ("YARD_SHUNT", "Yard Shunt", D.BOTH, [
        _step(1, L.YARD, L.YARD, M.NONE, S.NONE)]),
    ("BOBTAIL", "Bobtail", D.BOTH, [
        _step(1, None, None, M.NONE, S.NONE)]),
]


class LoadTypeTemplateService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = LoadTypeTemplateRepository(db, team_id)

    async def create(self, payload: LoadTypeTemplateCreateRequest, actor_user_id: int | None = None) -> LoadTypeTemplateResponseSchema:
        if await self.repo.find_by_code(payload.code):
            raise ConflictException(f"이미 존재하는 템플릿 코드: {payload.code}")
        header = payload.model_dump(exclude={"steps"})
        steps = [s.model_dump() for s in payload.steps]
        tpl = await self.repo.create(header, steps, actor_user_id=actor_user_id)
        return LoadTypeTemplateResponseSchema.model_validate(tpl)

    async def get(self, tpl_id: int) -> LoadTypeTemplateResponseSchema:
        tpl = await self.repo.get_with_steps(tpl_id)
        if not tpl:
            raise NotFoundException(_LABEL)
        return LoadTypeTemplateResponseSchema.model_validate(tpl)

    async def list_paginated(self, request: PaginateLoadTypeTemplateRequest) -> CursorPaginationResult[LoadTypeTemplateSummarySchema]:
        result = await self.repo.get_paginated(request)
        result.data = [LoadTypeTemplateSummarySchema.model_validate(r) for r in result.data]
        return result

    async def update(self, tpl_id: int, payload: LoadTypeTemplateUpdateRequest, actor_user_id: int | None = None) -> LoadTypeTemplateResponseSchema:
        tpl = await self.repo.update_header(tpl_id, payload.model_dump(exclude_unset=True), actor_user_id=actor_user_id)
        if not tpl:
            raise NotFoundException(_LABEL)
        return LoadTypeTemplateResponseSchema.model_validate(tpl)

    async def replace_steps(self, tpl_id: int, payload: TemplateStepsReplaceRequest, actor_user_id: int | None = None) -> LoadTypeTemplateResponseSchema:
        if not await self.repo.get_header(tpl_id):
            raise NotFoundException(_LABEL)
        tpl = await self.repo.replace_steps(tpl_id, [s.model_dump() for s in payload.steps], actor_user_id=actor_user_id)
        return LoadTypeTemplateResponseSchema.model_validate(tpl)

    async def delete(self, tpl_id: int, actor_user_id: int | None = None) -> LoadTypeTemplateDeleteResponseSchema:
        if not await self.repo.get_header(tpl_id):
            raise NotFoundException(_LABEL)
        await self.repo.soft_deactivate_by_id(tpl_id, actor_user_id=actor_user_id)
        return LoadTypeTemplateDeleteResponseSchema(id=tpl_id, deleted=True, soft_deleted=True)

    async def sync_delta(self, since_str: str):
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_delta(since)
        result.items = [LoadTypeTemplateSummarySchema.model_validate(r) for r in result.items]
        return result

    async def seed_defaults(self, actor_user_id: int | None = None) -> SeedDefaultsResponseSchema:
        """컨플루언스 16종 기본 템플릿 시드 (이미 있는 code 는 skip)."""
        created = skipped = 0
        for code, name, direction, steps in _DEFAULTS:
            if await self.repo.find_by_code(code):
                skipped += 1
                continue
            await self.repo.create(
                {"code": code, "name": name, "direction": direction, "is_system": True},
                steps, actor_user_id=actor_user_id,
            )
            created += 1
        return SeedDefaultsResponseSchema(created=created, skipped=skipped, total=len(_DEFAULTS))
