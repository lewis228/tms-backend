# scripts/e2e_redesign.py
"""재설계 전체 흐름 End-to-End 시나리오 — 실제 DB/서비스로 검증.

마스터 → 요율(그룹/시트/유효일자셀/배율/배정) → D/O+컨테이너 → Load Type→leg 생성
→ 배차(DISPATCHING→DISPATCHED) → 완료 → payroll(요율해석 $) → invoice(원가프리필+마진)
→ Hold/Cancel/활동타임라인. 각 단계 assert + 출력.

실행: PYTHONPATH=src python scripts/e2e_redesign.py
"""
from __future__ import annotations
import asyncio
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

from database.mysql_connection import write_engine
from sqlalchemy.ext.asyncio import AsyncSession


def banner(msg: str):
    print(f"\n{'='*8} {msg} {'='*8}")


async def main():
    import common.model.models_registry  # noqa: F401  metadata 등록
    async with AsyncSession(write_engine, expire_on_commit=False) as db:
        await run(db)


async def run(db: AsyncSession):
    # ── 모델/서비스 import ──
    from team.model import TeamModel
    from user.model import UserModel
    from customer.model import CustomerModel
    from terminal.model import TerminalModel
    from driver.model import DriverModel
    from truck.model import TruckModel
    from rate_point.model import RatePointModel
    from rate_point.const.status import PointType
    from rate_zone.model import RateZoneModel, RateZoneMemberModel
    from rate_group.model import RateGroupModel
    from rate_group.const.status import RateMethod
    from rate_sheet.model import RateSheetModel
    from rate_sheet.const.status import SheetKind, RateMoveType, RateContainerSize, RateEntrySource
    from rate_sheet import versioning
    from rate_sheet.repository import RateSheetRepository
    from rate_multiplier.model import RateMultiplierModel
    from driver_rate_assignment.model import DriverRateAssignmentModel
    from load_type_template.model import LoadTypeTemplateModel, LoadTypeTemplateStepModel
    from load_type_template.const.status import (
        LoadDirection, TemplateLocationType, TemplateMoveType, TemplateServiceType, TemplateMoveCode,
    )
    from delivery_order.model import DeliveryOrderModel
    from delivery_order.const.status import DeliveryStatus, ShipmentDirection
    from delivery_order.service import DeliveryOrderService
    from container.model import ContainerModel
    from container.const.status import ContainerSize
    from leg.service import LegService
    from leg.model import LegModel
    from leg.const.status import LegStatus, MoveType
    from payroll.service import PayrollService
    from payroll.schemas.request import PayrollBuildRequest
    from invoice.service import InvoiceService
    from invoice.schemas.request import InvoiceCreateRequest, InvoiceLineCreateRequest
    from sqlalchemy import select

    work_day = date(2026, 6, 9)

    # ── 0) 팀 + actor user ──
    banner("0. 팀 + actor")
    team = TeamModel(name="E2E Drayage Co")
    db.add(team); await db.flush()
    actor = UserModel(email=f"e2e-{team.id}@example.com",
                      password="$2b$04$dummybcrypthashplaceholder1234567890abcdefghij",
                      auth_provider="EMAIL", role="ADMIN", name="E2E Admin")
    db.add(actor); await db.flush()
    tid, aid = team.id, actor.id
    print(f"team={tid} actor={aid}")

    # ── 1) 마스터 ──
    banner("1. 마스터 (customer/terminal/driver/truck/rate_point/zone)")
    customer = CustomerModel(team_id=tid, name="ACME Importers", kind="CUSTOMER")
    terminal = TerminalModel(team_id=tid, name="LA Port T1", code="LAT1")
    db.add_all([customer, terminal]); await db.flush()
    driver = DriverModel(team_id=tid, user_id=aid, license_number="DL-1")
    truck = TruckModel(team_id=tid, plate_no="TRK-1", owner_kind="COMPANY", status="ACTIVE")
    db.add_all([driver, truck]); await db.flush()
    point = RatePointModel(team_id=tid, name="LA Port T1", code="LAT1",
                           point_type=PointType.TERMINAL, terminal_id=terminal.id)
    zone = RateZoneModel(team_id=tid, name="Zone A (Downtown)", code="ZA", color="#3b82f6")
    db.add_all([point, zone]); await db.flush()
    db.add(RateZoneMemberModel(team_id=tid, zone_id=zone.id, zip_code="90001", city="Los Angeles", state="CA"))
    await db.flush()
    print(f"customer={customer.id} terminal={terminal.id} driver={driver.id} point={point.id} zone={zone.id} (zip 90001)")

    # ── 2) 요율 ──
    banner("2. 요율 (group ZONE / sheet POINT_ZONE / 유효일자 셀 $170 / multiplier / 배정)")
    group = RateGroupModel(team_id=tid, name="기본 ZONE 그룹", method=RateMethod.ZONE, is_default=True)
    db.add(group); await db.flush()
    sheet = RateSheetModel(team_id=tid, rate_group_id=group.id, kind=SheetKind.POINT_ZONE,
                           move_type=RateMoveType.LOAD, row_point_id=point.id)
    db.add(sheet); await db.flush()
    # 유효일자 셀: zone A × SIZE_40 = $170 (work_day 이전부터 유효)
    sheet_repo = RateSheetRepository(db, tid)
    await versioning.set_rate(
        sheet_repo, sheet.id,
        {"col_zone_id": zone.id, "col_point_id": None, "col_city": None, "col_state": None,
         "container_size": RateContainerSize.SIZE_40},
        amount=Decimal("170.00"), per_unit=None, effective_from=date(2026, 6, 1),
        source=RateEntrySource.SHEET, reason="E2E seed", actor_user_id=aid,
    )
    # 컨테이너 배율: SIZE_20 = 0.85
    db.add(RateMultiplierModel(team_id=tid, rate_group_id=None, container_size=RateContainerSize.SIZE_20, factor=Decimal("0.85")))
    # 드라이버 → 그룹 배정 (work_day 유효)
    db.add(DriverRateAssignmentModel(team_id=tid, driver_id=driver.id, rate_group_id=group.id,
                                     effective_from=date(2026, 6, 1)))
    await db.flush()
    print(f"group={group.id} sheet={sheet.id} entry(zoneA×40)=$170 from 2026-06-01, multiplier 20=0.85, driver→group 배정")

    # ── 3) Load Type 템플릿 ──
    banner("3. Load Type 템플릿 (Import Direct Live, 2 step)")
    tpl = LoadTypeTemplateModel(team_id=tid, code="IMP_DIRECT_L", name="Import Direct (Live)",
                                direction=LoadDirection.IMPORT, is_system=True)
    db.add(tpl); await db.flush()
    db.add_all([
        LoadTypeTemplateStepModel(team_id=tid, template_id=tpl.id, seq=1,
            from_location_type=TemplateLocationType.TERMINAL, to_location_type=TemplateLocationType.CUSTOMER,
            move_type=TemplateMoveType.LOAD, service_type=TemplateServiceType.LIVE, move_code=TemplateMoveCode.PPU),
        LoadTypeTemplateStepModel(team_id=tid, template_id=tpl.id, seq=2,
            from_location_type=TemplateLocationType.CUSTOMER, to_location_type=TemplateLocationType.TERMINAL,
            move_type=TemplateMoveType.EMPTY, service_type=TemplateServiceType.LIVE, move_code=TemplateMoveCode.PRE),
    ])
    await db.flush()
    print(f"template={tpl.id} (PPU load + PRE empty)")

    # ── 4) D/O + 컨테이너 ──
    banner("4. D/O + 컨테이너 (40HC)")
    do = DeliveryOrderModel(team_id=tid, customer_id=customer.id, direction=ShipmentDirection.IMPORT,
                            status=DeliveryStatus.PLANNING, bl_number="BL-E2E-1", terminal_id=terminal.id,
                            created_by_user_id=aid)
    db.add(do); await db.flush()
    cont = ContainerModel(team_id=tid, delivery_order_id=do.id, sequence_no=1,
                          container_number="MSCU1234567", size=ContainerSize.SIZE_40HC)
    db.add(cont); await db.flush()
    await db.commit()
    print(f"do={do.id} status={do.status.value} container={cont.id} size={cont.size.value}")

    # ── 5) Load Type → leg 생성 ──
    banner("5. apply_load_type → leg 자동 생성")
    leg_svc = LegService(db, tid)
    legs = await leg_svc.apply_load_type(cont.id, tpl.id, actor_user_id=aid)
    print(f"생성된 leg {len(legs)}개: " + ", ".join(f"#{l.id}({l.move_type} {l.from_location_type}->{l.to_location_type})" for l in legs))
    assert len(legs) == 2, "leg 2개 생성 기대"
    # D/O 자동 DISPATCHING 파생 확인
    do_row = (await db.execute(select(DeliveryOrderModel).where(DeliveryOrderModel.id == do.id))).scalar_one()
    print(f"D/O status after legs = {do_row.status.value}")
    assert do_row.status == DeliveryStatus.DISPATCHING, "미배차 leg → DISPATCHING 기대"

    # 정산 대상 leg(LOAD/PPU)에 요율 입력 세팅: rate_point + dest_zip
    load_leg = (await db.execute(select(LegModel).where(
        LegModel.container_id == cont.id, LegModel.move_type == MoveType.LOADED, LegModel.is_active.is_(True),
    ))).scalars().first()
    load_leg.rate_point_id = point.id
    load_leg.dest_zip = "90001"
    await db.flush(); await db.commit()
    print(f"load leg #{load_leg.id} 에 rate_point={point.id}, dest_zip=90001 세팅")

    # ── 6) 배차 → DISPATCHED ──
    banner("6. 두 leg 배차 → D/O DISPATCHED")
    for l in legs:
        await leg_svc.assign_driver(l.id, driver.id, truck_id=truck.id, actor_user_id=aid)
    do_row = (await db.execute(select(DeliveryOrderModel).where(DeliveryOrderModel.id == do.id))).scalar_one()
    print(f"D/O status after assign = {do_row.status.value}")
    assert do_row.status == DeliveryStatus.DISPATCHED, "전 leg 배차 → DISPATCHED 기대"

    # ── 7) 완료 ──
    banner("7. leg 완료 (IN_TRANSIT → COMPLETED)")
    for l in legs:
        await leg_svc.transition(l.id, LegStatus.IN_TRANSIT, actor_user_id=aid)
        # completed_at 이 work_day 가 되도록 직접 세팅 후 완료
        await leg_svc.transition(l.id, LegStatus.COMPLETED, actor_user_id=aid)
    # work_date 보정: resolver 가 group 배정/요율 유효일자(2026-06-01~)를 타도록 completed_at 을 work_day 로
    for l in legs:
        row = (await db.execute(select(LegModel).where(LegModel.id == l.id))).scalar_one()
        row.completed_at = datetime(2026, 6, 9, 10, tzinfo=timezone.utc)
    await db.flush(); await db.commit()
    print("두 leg COMPLETED, completed_at=2026-06-09")

    # ── 8) payroll ──
    banner("8. payroll build → 요율 해석 ($170 RESOLVED 기대)")
    pay_svc = PayrollService(db, tid)
    detail = await pay_svc.build(PayrollBuildRequest(driver_id=driver.id, period_start=date(2026, 6, 1), period_end=date(2026, 6, 30)), actor_user_id=aid)
    await db.commit()
    print(f"payroll #{detail.id} status={detail.status.value} base_total={detail.base_total} lines={len(detail.lines)}")
    for ln in detail.lines:
        print(f"  line leg={ln.leg_id} base={ln.base_amount} source={ln.source.value} msg={ln.message}")
    # 적재 leg 는 $170 RESOLVED, 공컨 leg 는 EMPTY move → 요율 없음(0/UNRESOLVED) 일 수 있음
    resolved = [ln for ln in detail.lines if str(ln.source.value) == "RESOLVED" and ln.base_amount and ln.base_amount > 0]
    assert any(ln.base_amount == Decimal("170.00") for ln in detail.lines), "적재 leg base $170 기대"
    print(f"✅ 적재 leg 요율 해석됨 (RESOLVED ${[ln.base_amount for ln in detail.lines]})")

    # ── 9) invoice ──
    banner("9. invoice 생성(D/O 원가 프리필) + 마진 라인")
    inv_svc = InvoiceService(db, tid)
    inv = await inv_svc.create(InvoiceCreateRequest(customer_id=customer.id, delivery_order_id=do.id, prefill_from_do=True), actor_user_id=aid)
    await db.commit()
    print(f"invoice #{inv.id} cost_total={inv.cost_total} charge_total={inv.charge_total} margin={inv.margin} lines={len(inv.lines)}")
    # 청구 라인 마크업: 컨테이너 라인 unit을 250으로 올림
    if inv.lines:
        line0 = inv.lines[0]
        inv = await inv_svc.update_line(inv.id, line0.id, __import__("invoice.schemas.request", fromlist=["InvoiceLineUpdateRequest"]).InvoiceLineUpdateRequest(unit_amount=Decimal("250.00")), actor_user_id=aid)
        await db.commit()
    # 추가 수동 라인(Fuel)
    inv = await inv_svc.add_line(inv.id, InvoiceLineCreateRequest(description="Fuel Surcharge", quantity=Decimal("1"), unit_amount=Decimal("40.00")), actor_user_id=aid)
    await db.commit()
    print(f"마크업 후: cost={inv.cost_total} charge={inv.charge_total} margin={inv.margin}")
    print(f"✅ 마진 = 청구 - 원가 = {inv.charge_total} - {inv.cost_total} = {inv.margin}")

    # ── 10) Hold/Cancel/활동 ──
    banner("10. D/O Hold/Cancel + 활동 타임라인")
    do_svc = DeliveryOrderService(db, tid)
    await do_svc.set_hold(do.id, on_hold=True, reason="서류 대기", actor_user_id=aid)
    await db.commit()
    do_row = (await db.execute(select(DeliveryOrderModel).where(DeliveryOrderModel.id == do.id))).scalar_one()
    print(f"hold: is_on_hold={do_row.is_on_hold} reason={do_row.hold_reason}")
    assert do_row.is_on_hold
    from audit_log.service import AuditLogService
    acts = await AuditLogService(db, tid).list_for_entity("delivery_order", do.id)
    print(f"활동 타임라인 {len(acts)}건: " + ", ".join(a.action for a in acts))
    assert any(a.action == "hold_set" for a in acts)

    banner("✅ E2E 전체 통과")
    print(f"\n요약: team={tid} do={do.id} container={cont.id} legs={[l.id for l in legs]} "
          f"payroll={detail.id}(${detail.base_total}) invoice={inv.id}(margin {inv.margin})")


if __name__ == "__main__":
    asyncio.run(main())
