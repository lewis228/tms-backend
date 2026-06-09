# scripts/seed_redesign_demo.py
"""프론트 클릭 점검용 데모 시드 — 로그인 계정 + 멤버십 + 어드민 권한그룹 + 재설계 풀데이터.

- 데모 팀 "TMS 데모" (onboarding 완료)
- 로그인: demo@omniq.dev / Demo1234!  (ADMIN, 어드민 권한그룹 → 모든 permission_guard 바이패스)
- 마스터/요율/Load Type/D-O/컨테이너/leg/배차/완료/payroll/invoice 시드 (E2E 검증 흐름)
- E2E 임시 team 정리

실행: PYTHONPATH=src python scripts/seed_redesign_demo.py
"""
from __future__ import annotations
import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

import bcrypt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database.mysql_connection import write_engine

DEMO_EMAIL = "demo@omniq.dev"
DEMO_PW = "Demo1234!"
TEST_EMAIL = "test@test.com"
TEST_PW = "1234"


def banner(m): print(f"\n{'='*8} {m} {'='*8}")


async def main():
    import common.model.models_registry  # noqa: F401
    async with AsyncSession(write_engine, expire_on_commit=False) as db:
        await cleanup(db)
        await seed(db)


async def cleanup(db: AsyncSession):
    """기존 demo/test + E2E 임시 데이터 제거 + 고아 행 정리.

    팀 내부 RESTRICT FK(delivery_order→customer 등) 때문에 단순 `DELETE FROM teams`
    CASCADE 는 순서 문제로 실패한다. 그래서 FK_CHECKS=0 으로 끄되, 대상 팀의
    **모든** team-scoped 행을 명시적으로 지워 고아를 남기지 않는다.
    """
    banner("정리: 기존 demo/test + E2E 임시 데이터 + 고아 행 제거")
    import common.model.models_registry  # noqa: F401
    from common.model.team_scoped_mixin import get_team_scoped_table_names
    from sqlalchemy import bindparam
    from user.model import UserModel
    from team.model import TeamModel, UserTeamModel

    tables = get_team_scoped_table_names()

    # 1) 제거 대상 팀 id 수집 — demo/test 유저의 멤버십 팀 + E2E 임시 팀
    target_team_ids: set[int] = set()
    login_user_ids: set[int] = set()
    for em in (DEMO_EMAIL, TEST_EMAIL):
        u = (await db.execute(select(UserModel).where(UserModel.email == em))).scalar_one_or_none()
        if not u:
            continue
        login_user_ids.add(u.id)
        for m in (await db.execute(select(UserTeamModel).where(UserTeamModel.user_id == u.id))).scalars().all():
            target_team_ids.add(m.team_id)
    for t in (await db.execute(select(TeamModel).where(TeamModel.name == "E2E Drayage Co"))).scalars().all():
        target_team_ids.add(t.id)

    await db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    # 2) 대상 팀의 모든 team-scoped 행 삭제 (고아 방지)
    if target_team_ids:
        for tbl in tables:
            await db.execute(
                text(f"DELETE FROM {tbl} WHERE team_id IN :v").bindparams(bindparam("v", expanding=True)),
                {"v": list(target_team_ids)},
            )
        await db.execute(
            text("DELETE FROM user_team WHERE team_id IN :v").bindparams(bindparam("v", expanding=True)),
            {"v": list(target_team_ids)},
        )
        await db.execute(
            text("DELETE FROM teams WHERE id IN :v").bindparams(bindparam("v", expanding=True)),
            {"v": list(target_team_ids)},
        )
    # 3) 로그인 유저 + E2E actor 제거
    if login_user_ids:
        await db.execute(
            text("DELETE FROM user_team WHERE user_id IN :v").bindparams(bindparam("v", expanding=True)),
            {"v": list(login_user_ids)},
        )
        await db.execute(
            text("DELETE FROM user WHERE id IN :v").bindparams(bindparam("v", expanding=True)),
            {"v": list(login_user_ids)},
        )
    await db.execute(text("DELETE FROM user WHERE email LIKE 'e2e-%@example.com'"))
    # 4) 혹시 남은 고아(team_id 가 더 이상 없는 행) 일괄 정리
    valid = [r[0] for r in (await db.execute(text("SELECT id FROM teams"))).fetchall()] or [0]
    orphans = 0
    for tbl in tables:
        res = await db.execute(
            text(f"DELETE FROM {tbl} WHERE team_id NOT IN :v").bindparams(bindparam("v", expanding=True)),
            {"v": valid},
        )
        orphans += res.rowcount or 0
    await db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    print(f"  제거 팀 {len(target_team_ids)}개, 로그인유저 {len(login_user_ids)}, 고아 {orphans}행")
    await db.commit()


async def seed(db: AsyncSession):
    from team.model import TeamModel, UserTeamModel
    from user.model import UserModel
    from rbac.model import PermissionGroupModel
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
        LoadDirection, TemplateLocationType as L, TemplateMoveType as M,
        TemplateServiceType as S, TemplateMoveCode as MC,
    )
    from delivery_order.model import DeliveryOrderModel
    from delivery_order.const.status import DeliveryStatus, ShipmentDirection
    from container.model import ContainerModel
    from container.const.status import ContainerSize
    from leg.service import LegService
    from leg.model import LegModel
    from leg.const.status import LegStatus, MoveType
    from payroll.service import PayrollService
    from payroll.schemas.request import PayrollBuildRequest
    from invoice.service import InvoiceService
    from invoice.schemas.request import InvoiceCreateRequest, InvoiceLineCreateRequest, InvoiceLineUpdateRequest

    banner("데모 팀 + 로그인 + 어드민 권한그룹")
    team = TeamModel(name="TMS 데모", onboarding_step1_done=True, onboarding_step2_done=True,
                     onboarding_step3_done=True, onboarding_completed=True,
                     currency="USD", decimal_places=2, timezone="America/Los_Angeles")
    db.add(team); await db.flush()
    pw_hash = bcrypt.hashpw(DEMO_PW.encode(), bcrypt.gensalt()).decode()
    user = UserModel(email=DEMO_EMAIL, password=pw_hash, auth_provider="EMAIL",
                     role="ADMIN", name="데모 관리자")
    db.add(user); await db.flush()
    grp = PermissionGroupModel(team_id=team.id, name="관리자", is_admin=True, is_system=True,
                               system_key="ADMIN", version=1)
    db.add(grp); await db.flush()
    db.add(UserTeamModel(user_id=user.id, team_id=team.id, permission_group_id=grp.id))
    # 두 번째 로그인 계정 — test@test.com / 1234 (같은 팀, 어드민)
    test_user = UserModel(email=TEST_EMAIL, password=bcrypt.hashpw(TEST_PW.encode(), bcrypt.gensalt()).decode(),
                          auth_provider="EMAIL", role="ADMIN", name="Test User")
    db.add(test_user); await db.flush()
    db.add(UserTeamModel(user_id=test_user.id, team_id=team.id, permission_group_id=grp.id))
    await db.flush()
    tid, aid = team.id, user.id
    print(f"  team={tid}  로그인: {DEMO_EMAIL}/{DEMO_PW}  &  {TEST_EMAIL}/{TEST_PW}  (admin group={grp.id})")

    banner("마스터 + 요율 + Load Type")
    customer = CustomerModel(team_id=tid, name="ACME Importers", kind="CUSTOMER")
    cust2 = CustomerModel(team_id=tid, name="Globex Logistics", kind="CUSTOMER")
    terminal = TerminalModel(team_id=tid, name="LA Port T1", code="LAT1")
    db.add_all([customer, cust2, terminal]); await db.flush()
    driver = DriverModel(team_id=tid, user_id=aid, license_number="DL-1001")
    truck = TruckModel(team_id=tid, plate_no="TRK-100", owner_kind="COMPANY", status="ACTIVE")
    db.add_all([driver, truck]); await db.flush()
    point = RatePointModel(team_id=tid, name="LA Port T1", code="LAT1",
                           point_type=PointType.TERMINAL, terminal_id=terminal.id)
    zone = RateZoneModel(team_id=tid, name="Zone A (Downtown LA)", code="ZA", color="#3b82f6")
    db.add_all([point, zone]); await db.flush()
    db.add(RateZoneMemberModel(team_id=tid, zone_id=zone.id, zip_code="90001", city="Los Angeles", state="CA"))
    group = RateGroupModel(team_id=tid, name="기본 ZONE 그룹", method=RateMethod.ZONE, is_default=True)
    db.add(group); await db.flush()
    sheet = RateSheetModel(team_id=tid, rate_group_id=group.id, kind=SheetKind.POINT_ZONE,
                           move_type=RateMoveType.LOAD, row_point_id=point.id)
    db.add(sheet); await db.flush()
    await versioning.set_rate(
        RateSheetRepository(db, tid), sheet.id,
        {"col_zone_id": zone.id, "col_point_id": None, "col_city": None, "col_state": None,
         "container_size": RateContainerSize.SIZE_40},
        amount=Decimal("170.00"), per_unit=None, effective_from=date(2026, 6, 1),
        source=RateEntrySource.SHEET, reason="데모 시드", actor_user_id=aid,
    )
    db.add(RateMultiplierModel(team_id=tid, rate_group_id=None, container_size=RateContainerSize.SIZE_20, factor=Decimal("0.85")))
    db.add(DriverRateAssignmentModel(team_id=tid, driver_id=driver.id, rate_group_id=group.id, effective_from=date(2026, 6, 1)))
    tpl = LoadTypeTemplateModel(team_id=tid, code="IMP_DIRECT_L", name="Import Direct (Live)",
                                direction=LoadDirection.IMPORT, is_system=True)
    db.add(tpl); await db.flush()
    db.add_all([
        LoadTypeTemplateStepModel(team_id=tid, template_id=tpl.id, seq=1, from_location_type=L.TERMINAL,
            to_location_type=L.CUSTOMER, move_type=M.LOAD, service_type=S.LIVE, move_code=MC.PPU),
        LoadTypeTemplateStepModel(team_id=tid, template_id=tpl.id, seq=2, from_location_type=L.CUSTOMER,
            to_location_type=L.TERMINAL, move_type=M.EMPTY, service_type=S.LIVE, move_code=MC.PRE),
    ])
    await db.commit()
    print("  customer×2, terminal, driver, truck, rate_point, zone(zip 90001), ZONE그룹/시트/셀($170)/배율/배정, LoadType 템플릿")

    banner("D/O #1 (완주: 배차→완료→정산→인보이스)")
    do = DeliveryOrderModel(team_id=tid, customer_id=customer.id, direction=ShipmentDirection.IMPORT,
                            status=DeliveryStatus.PLANNING, bl_number="MAEU-1234567",
                            booking_number="BK-001", terminal_id=terminal.id, created_by_user_id=aid)
    db.add(do); await db.flush()
    cont = ContainerModel(team_id=tid, delivery_order_id=do.id, sequence_no=1,
                          container_number="MSCU1234567", size=ContainerSize.SIZE_40HC)
    db.add(cont); await db.flush(); await db.commit()
    leg_svc = LegService(db, tid)
    legs = await leg_svc.apply_load_type(cont.id, tpl.id, actor_user_id=aid)
    load_leg = (await db.execute(select(LegModel).where(
        LegModel.container_id == cont.id, LegModel.move_type == MoveType.LOADED, LegModel.is_active.is_(True),
    ))).scalars().first()
    load_leg.rate_point_id = point.id; load_leg.dest_zip = "90001"
    await db.flush(); await db.commit()
    for l in legs:
        await leg_svc.assign_driver(l.id, driver.id, truck_id=truck.id, actor_user_id=aid)
    for l in legs:
        await leg_svc.transition(l.id, LegStatus.IN_TRANSIT, actor_user_id=aid)
        await leg_svc.transition(l.id, LegStatus.COMPLETED, actor_user_id=aid)
    for l in legs:
        row = (await db.execute(select(LegModel).where(LegModel.id == l.id))).scalar_one()
        row.completed_at = datetime(2026, 6, 9, 10, tzinfo=timezone.utc)
    await db.flush(); await db.commit()
    pay = await PayrollService(db, tid).build(PayrollBuildRequest(driver_id=driver.id, period_start=date(2026, 6, 1), period_end=date(2026, 6, 30)), actor_user_id=aid)
    await db.commit()
    inv_svc = InvoiceService(db, tid)
    inv = await inv_svc.create(InvoiceCreateRequest(customer_id=customer.id, delivery_order_id=do.id, invoice_number="INV-001", prefill_from_do=True), actor_user_id=aid)
    await db.commit()
    if inv.lines:
        inv = await inv_svc.update_line(inv.id, inv.lines[0].id, InvoiceLineUpdateRequest(unit_amount=Decimal("250.00")), actor_user_id=aid)
        await db.commit()
    inv = await inv_svc.add_line(inv.id, InvoiceLineCreateRequest(description="Fuel Surcharge", unit_amount=Decimal("40.00")), actor_user_id=aid)
    await db.commit()
    do1 = (await db.execute(select(DeliveryOrderModel).where(DeliveryOrderModel.id == do.id))).scalar_one()
    print(f"  D/O #{do.id} status={do1.status.value}, payroll #{pay.id} ${pay.base_total}, invoice #{inv.id} 마진 ${inv.margin}")

    banner("D/O #2 (PLANNING — 배차 전)")
    do2 = DeliveryOrderModel(team_id=tid, customer_id=cust2.id, direction=ShipmentDirection.EXPORT,
                             status=DeliveryStatus.PLANNING, bl_number="ONEY-7654321",
                             booking_number="BK-002", terminal_id=terminal.id, created_by_user_id=aid)
    db.add(do2); await db.flush()
    db.add(ContainerModel(team_id=tid, delivery_order_id=do2.id, sequence_no=1,
                          container_number="TCLU7654321", size=ContainerSize.SIZE_20GP))
    await db.flush(); await db.commit()
    print(f"  D/O #{do2.id} PLANNING (export, 20GP)")

    banner("✅ 데모 시드 완료")
    print(f"""
로그인: {TEST_EMAIL} / {TEST_PW}   또는   {DEMO_EMAIL} / {DEMO_PW}
팀: TMS 데모 (id={tid})
화면: 요율(rates/*), 마스터, D/O #{do.id}(완주)·#{do2.id}(planning),
 Shipment 상세(탭), 정산 #{pay.id}, 인보이스 #{inv.id}, 대시보드
""")


if __name__ == "__main__":
    asyncio.run(main())
