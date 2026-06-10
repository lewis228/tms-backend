# src/rate_sheet/resolve.py
"""요율 종합 해석 엔진 — driver → 유효 요율그룹 → method 분기 → 단가 산출.

payroll/invoice 가 정산·청구 시점에 사용. payroll.resolve.resolve_leg_rate 가 leg 의
(driver, work_date, move_type, rate_point, dest_zip/city, container_size, miles/hours) 를
뽑아 이 RateResolver.resolve 를 호출하고, 결과 base 를 payroll_line 에 snapshot 동결한다.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from rate_sheet.repository import RateSheetRepository
from rate_sheet import lookup
from rate_sheet.const.status import SheetKind, RateMoveType, RateServiceType, RateContainerSize
from rate_sheet.schemas.response import RateResolveResultSchema
from rate_group.repository import RateGroupRepository
from rate_group.const.status import RateMethod
from rate_zone.repository import RateZoneRepository
from rate_multiplier.service import RateMultiplierService
from driver_rate_assignment.service import DriverRateAssignmentService


def _fail(msg: str, **kw) -> RateResolveResultSchema:
    return RateResolveResultSchema(found=False, message=msg, **kw)


class RateResolver:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.sheet_repo = RateSheetRepository(db, team_id)
        self.group_repo = RateGroupRepository(db, team_id)
        self.zone_repo = RateZoneRepository(db, team_id)
        self.mult_svc = RateMultiplierService(db, team_id)
        self.dra_svc = DriverRateAssignmentService(db, team_id)

    async def resolve(
        self, *, driver_id: int, work_date: date,
        move_type: RateMoveType | None = None, row_point_id: int | None = None,
        service_type: RateServiceType | None = None,
        dest_zip: str | None = None, dest_city: str | None = None, dest_state: str | None = None,
        container_size: RateContainerSize | None = None,
        miles: Decimal | None = None, hours: Decimal | None = None,
    ) -> RateResolveResultSchema:
        # 1) 드라이버 → 유효 요율그룹
        assign = await self.dra_svc.get_active_for_driver(driver_id, work_date)
        if assign is None:
            return _fail(f"드라이버(id={driver_id}) 의 {work_date.isoformat()} 기준 요율그룹 배정이 없습니다.")
        group = await self.group_repo.get(assign.rate_group_id)
        if group is None:
            return _fail("배정된 요율그룹이 비활성/삭제되었습니다.", rate_group_id=assign.rate_group_id)
        gid = group.id
        method = group.method

        # 2) method 분기
        if method in (RateMethod.MILE, RateMethod.HOURLY):
            kind = SheetKind.MILE if method == RateMethod.MILE else SheetKind.HOURLY
            qty = miles if method == RateMethod.MILE else hours
            sheet = await self.sheet_repo.find_slot(gid, kind, None, None)
            if sheet is None:
                return _fail(f"{method.value} 시트가 없습니다.", method=method.value, rate_group_id=gid)
            empty_cell = {k: None for k in ("col_zone_id", "col_point_id", "col_city", "col_state", "container_size")}
            lk = await lookup.resolve_cell(self.sheet_repo, sheet.id, empty_cell, work_date)
            if not lk.found or lk.per_unit is None:
                return _fail(lk.message or "단가 미등록", method=method.value, rate_group_id=gid, rate_sheet_id=sheet.id)
            q = qty if qty is not None else Decimal("0")
            base = (lk.per_unit * q).quantize(Decimal("0.01"))
            return RateResolveResultSchema(
                found=True, method=method.value, rate_group_id=gid, rate_sheet_id=sheet.id,
                rate_entry_id=lk.rate_entry_id, per_unit=lk.per_unit, quantity=q, base_amount=base,
            )

        # ZONE / CITY 매트릭스
        if move_type is None or row_point_id is None:
            return _fail("ZONE/CITY 해석에는 move_type 과 row_point_id 가 필요합니다.", method=method.value, rate_group_id=gid)
        kind = SheetKind.POINT_ZONE if method == RateMethod.ZONE else SheetKind.POINT_CITY
        # 컨플루언스 'Leg 전체 유형': service_type 별 요율 우선, 없으면 service_type 무관(NULL) 슬롯 폴백.
        sheet = await self.sheet_repo.find_slot(gid, kind, move_type, row_point_id, service_type=service_type)
        if sheet is None and service_type is not None:
            sheet = await self.sheet_repo.find_slot(gid, kind, move_type, row_point_id, service_type=None)
        if sheet is None:
            return _fail(
                f"{method.value} 시트가 없습니다 (move={move_type.value}, "
                f"service={service_type.value if service_type else None}, point={row_point_id}).",
                method=method.value, rate_group_id=gid)

        zone_id = None
        if method == RateMethod.ZONE:
            if not dest_zip:
                return _fail("ZONE 해석에는 dest_zip 이 필요합니다.", method=method.value, rate_group_id=gid, rate_sheet_id=sheet.id)
            zone_id = await self.zone_repo.resolve_zone_id_by_zip(dest_zip)
            if zone_id is None:
                return _fail(f"zip={dest_zip} 에 매핑된 Zone 이 없습니다.", method=method.value, rate_group_id=gid, rate_sheet_id=sheet.id)
            coord = {"col_zone_id": zone_id, "col_point_id": None, "col_city": None, "col_state": None}
        else:  # CITY
            if not dest_city:
                return _fail("CITY 해석에는 dest_city 가 필요합니다.", method=method.value, rate_group_id=gid, rate_sheet_id=sheet.id)
            coord = {"col_zone_id": None, "col_point_id": None, "col_city": dest_city, "col_state": dest_state}

        # 사이즈 해석: ① 요청 사이즈 셀(오버라이드/정확값) 우선 → 그대로 사용(배율 1.0)
        #             ② 없으면 40ft 마스터 셀 × 배율(20/45). Bobtail(size=None) 은 배율 미적용.
        exact = await lookup.resolve_cell(self.sheet_repo, sheet.id, {**coord, "container_size": container_size}, work_date)
        if exact.found and exact.amount is not None:
            base = exact.amount.quantize(Decimal("0.01"))
            return RateResolveResultSchema(
                found=True, method=method.value, rate_group_id=gid, rate_sheet_id=sheet.id,
                rate_entry_id=exact.rate_entry_id, zone_id=zone_id, amount=exact.amount,
                multiplier=Decimal("1.00"), base_amount=base,
            )

        if container_size is not None and container_size != RateContainerSize.SIZE_40:
            master = await lookup.resolve_cell(self.sheet_repo, sheet.id, {**coord, "container_size": RateContainerSize.SIZE_40}, work_date)
            if master.found and master.amount is not None:
                factor = await self.mult_svc.get_factor(container_size, gid)
                base = (master.amount * factor).quantize(Decimal("0.01"))
                return RateResolveResultSchema(
                    found=True, method=method.value, rate_group_id=gid, rate_sheet_id=sheet.id,
                    rate_entry_id=master.rate_entry_id, zone_id=zone_id, amount=master.amount,
                    multiplier=factor, base_amount=base,
                )

        return _fail(
            f"요율 미등록 (sheet={sheet.id}, size={container_size}, date={work_date.isoformat()}).",
            method=method.value, rate_group_id=gid, rate_sheet_id=sheet.id, zone_id=zone_id,
        )
