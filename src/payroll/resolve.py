# src/payroll/resolve.py
"""leg → RateResolver 입력 매핑 = 신규 요율엔진과 정산의 연결점.

leg 의 (driver, 완료일, move_type, origin_zip/city, dest_zip/city, miles/hours) 를
RateResolver.resolve 입력으로 변환해 base 요율을 해석한다. 결과는 정산 라인에 snapshot.
"""
from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from rate_sheet.resolve import RateResolver
from rate_sheet.const.status import RateMoveType, RateServiceType
from rate_sheet.schemas.response import RateResolveResultSchema
from leg.model import LegModel
from leg.const.status import MoveType, ServiceType

_MOVE_MAP = {
    MoveType.LOADED: RateMoveType.LOAD,
    MoveType.EMPTY: RateMoveType.EMPTY,
    MoveType.BOBTAIL: RateMoveType.NONE,
}
_SVC_MAP = {
    ServiceType.LIVE: RateServiceType.LIVE,
    ServiceType.DROP: RateServiceType.DROP,
    ServiceType.NONE: RateServiceType.NONE,
}


async def resolve_leg_rate(db: AsyncSession, team_id: int, leg: LegModel) -> RateResolveResultSchema:
    if leg.driver_id is None:
        return RateResolveResultSchema(found=False, message="드라이버 미배정 leg")
    work_date = (leg.completed_at or leg.assigned_at or datetime.now(timezone.utc)).date()
    move = _MOVE_MAP.get(leg.move_type, RateMoveType.NONE)

    return await RateResolver(db, team_id).resolve(
        driver_id=leg.driver_id, work_date=work_date, move_type=move,
        service_type=_SVC_MAP.get(leg.service_type),
        from_zip=leg.origin_zip, from_city=leg.origin_city, from_state=leg.origin_state,
        dest_zip=leg.dest_zip, dest_city=leg.dest_city, dest_state=leg.dest_state,
        miles=leg.rate_miles, hours=leg.rate_hours,
    )
