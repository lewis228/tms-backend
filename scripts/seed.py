# scripts/seed.py
"""TMS 통합 시드 — DB를 통째로 비우고 모든 테이블에 데이터를 한 번에 채운다.

- 실행:   PYTHONPATH=src python scripts/seed.py
- 멱등:   매 실행마다 전 테이블 TRUNCATE 후 새로 삽입 → 항상 동일한 깨끗한 상태.
- 로그인: test@test.com / 1234  (role=ADMIN, 팀 ADMIN 권한그룹 → 모든 화면 접근)
- 커버:   alembic_version 제외 모든 비즈니스 테이블(49개)에 ≥1 행. 말미에 전수 단언.

기존 seed_local.py / seed_redesign_demo.py / e2e_redesign.py 를 하나로 통합.
"""
from __future__ import annotations
import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import common.model.models_registry  # noqa: F401  (49개 모델 전부 등록)
from common.model.base_model import Base
from database.mysql_connection import write_engine

# ── 로그인 ───────────────────────────────────────────────────
LOGIN_EMAIL = "test@test.com"
LOGIN_PW = "1234"
NOW = datetime(2026, 6, 9, 10, 0, tzinfo=timezone.utc)
TODAY = date(2026, 6, 9)


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def banner(m: str):
    print(f"\n{'=' * 10} {m} {'=' * 10}")


async def wipe(db: AsyncSession):
    """alembic_version 제외 전 테이블 TRUNCATE (FK 무시)."""
    banner("WIPE — 전 테이블 비우기")
    names = [r[0] for r in (await db.execute(text("SHOW TABLES"))).all()]
    await db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    for n in names:
        if n == "alembic_version":
            continue
        await db.execute(text(f"TRUNCATE TABLE `{n}`"))
    await db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    await db.commit()
    print(f"  {len(names) - 1}개 테이블 비움")


async def seed(db: AsyncSession):
    # ── enum / model imports ──────────────────────────────────
    from user.model import UserModel
    from user.const.roles import RolesEnum
    from team.model import TeamModel, UserTeamModel
    from rbac.model import PermissionModel, PermissionGroupModel, PermissionGroupPermission
    from rbac.const.const import ALL_PERMISSION_CODES, GROUP_DEFAULTS_BY_SYSTEM_KEY
    from file.model import FileAssetModel
    from file.const.domains import FileDomain
    from customer.model import CustomerModel
    from customer.const.status import PartnerKind
    from terminal.model import TerminalModel
    from vessel.model import VesselModel
    from location.model import LocationModel
    from location.const.kind import LocationKind
    from equipment_pool.model import EquipmentPoolModel
    from equipment_pool.const.status import EquipmentPoolKind
    from driver.model import DriverModel
    from driver.const.status import DutyStatus, EmploymentKind, PaymentTermsKind
    from truck.model import TruckModel
    from truck.const.status import TruckOwnerKind, TruckStatus
    from chassis.model import ChassisModel
    from chassis.const.status import ChassisSize, ChassisOwnerKind, ChassisStatus
    from addon.service import AddonService
    from addon.model import AddonModel
    from addon.const.status import AddonCategory, AddonUnit
    from rate_zone.model import RateZoneModel, RateZoneMemberModel
    from rate_group.model import RateGroupModel
    from rate_group.const.status import RateMethod
    from rate_group.entry_service import RateGroupEntryService
    from rate_group.schemas.request import FlatRateEntryRequest
    from rate_multiplier.model import RateMultiplierModel
    from rate_sheet.const.status import RateMoveType, RateServiceType, RateContainerSize
    from driver_rate_assignment.model import DriverRateAssignmentModel
    from load_type_template.service import LoadTypeTemplateService
    from delivery_order.model import DeliveryOrderModel, DeliveryOrderAddonModel
    from delivery_order.const.status import DeliveryStatus, ShipmentDirection
    from container.model import ContainerModel, ContainerEventModel
    from container.const.status import ContainerSize, ContainerEventKind
    from container_stop.model import ContainerStopModel
    from leg.model import LegModel
    from leg.const.status import (
        PointType, MoveType, ServiceType, ContainerState, LegStatus,
        LegMoveCode, HandoverReason, ChassisEventKind,
    )
    from leg_layer.model import LegAddonModel
    from leg_driver_segment.model import LegDriverSegmentModel
    from chassis_event.model import ChassisEventModel
    from street_turn.model import StreetTurnModel
    from street_turn.const.link_type import StreetTurnLinkType
    from street_turn.const.status import StreetTurnStatus
    from dual_transaction.model import DualTransactionModel
    from dual_transaction.const.status import DualTransactionStatus
    from payroll.model import PayrollSettlementModel, PayrollLineModel, PayrollChargeModel
    from payroll.const.status import PayrollStatus, PayrollLineSource
    from invoice.model import InvoiceModel, InvoiceLineModel
    from invoice.const.status import InvoiceStatus, InvoiceLineSource
    from notification.model import NotificationModel
    from notification.const.channel import NotificationChannel, NotificationStatus
    from chat.model import ChatMessageModel
    from chat.const.sender import ChatSenderType
    from location_ping.model import LocationPingModel
    from push_token.model import PushTokenModel
    from api_key.model import ApiKeyModel
    from audit_log.model import AuditLogModel

    D = Decimal

    # ── 1. RBAC / 전역 ────────────────────────────────────────
    banner("RBAC · 유저 · 팀")
    perms = [PermissionModel(code=c, label=c.replace("_", " ").title(), category="seed",
                             description=f"{c} permission") for c in ALL_PERMISSION_CODES]
    db.add_all(perms)
    await db.flush()
    code_to_pid = {p.code: p.id for p in perms}

    admin = UserModel(email=LOGIN_EMAIL, password=_hash(LOGIN_PW), auth_provider="EMAIL",
                      role=RolesEnum.ADMIN, name="Test Admin", phone="+1-310-000-0001")
    dispatcher = UserModel(email="dispatch@test.com", password=_hash(LOGIN_PW), auth_provider="EMAIL",
                           role=RolesEnum.DISPATCHER, name="Dana Dispatcher", phone="+1-310-000-0002")
    duser = [
        UserModel(email=f"driver{i}@test.com", password=_hash(LOGIN_PW), auth_provider="EMAIL",
                  role=RolesEnum.DRIVER, name=f"Driver {i}", phone=f"+1-310-000-01{i:02d}")
        for i in (1, 2, 3)
    ]
    db.add_all([admin, dispatcher, *duser])
    await db.flush()
    aid = admin.id

    team = TeamModel(
        name="TMS Demo Drayage Co", onboarding_step1_done=True, onboarding_step2_done=True,
        onboarding_step3_done=True, onboarding_completed=True, currency="USD", currency_symbol="$",
        decimal_places=2, timezone="America/Los_Angeles", company_name="TMS Demo Drayage Co.",
        representative_name="Test Admin", phone_number="+1-310-555-1000", address="123 Harbor Blvd, Long Beach, CA",
        created_by_user_id=aid,
    )
    db.add(team)
    await db.flush()
    tid = team.id

    # 권한 그룹 3종 (ADMIN/MEMBER/VIEWER) + 매핑
    groups = {}
    for key, name in (("ADMIN", "Administrators"), ("MEMBER", "Dispatchers"), ("VIEWER", "Viewers")):
        g = PermissionGroupModel(team_id=tid, name=name, is_admin=(key == "ADMIN"),
                                 is_system=True, system_key=key, version=1, created_by_user_id=aid)
        db.add(g)
        await db.flush()
        groups[key] = g
        for code in GROUP_DEFAULTS_BY_SYSTEM_KEY.get(key, []):
            pid = code_to_pid.get(code)
            if pid:
                db.add(PermissionGroupPermission(team_id=tid, group_id=g.id, permission_id=pid))

    # 멤버십
    db.add(UserTeamModel(user_id=admin.id, team_id=tid, permission_group_id=groups["ADMIN"].id))
    db.add(UserTeamModel(user_id=dispatcher.id, team_id=tid, permission_group_id=groups["MEMBER"].id))
    for u in duser:
        db.add(UserTeamModel(user_id=u.id, team_id=tid, permission_group_id=None))  # driver=role 가드
    await db.flush()
    print(f"  team={tid}, 권한 {len(perms)}개, 그룹 3, 로그인 {LOGIN_EMAIL}/{LOGIN_PW}")

    # ── zip 마스터 적재 (전역) — 외부 GeoNames, 시드는 CA만(reset 빠르게) ──
    banner("zip 마스터 (외부 적재)")
    from import_zips import load_zip_codes
    # 주요 항만·드레이지 주들 (LA/LB·NY/NJ·Savannah·Houston·Seattle·Chicago·Miami 등)
    await load_zip_codes(db, states=["CA", "NV", "AZ", "TX", "NJ", "NY", "GA", "FL", "WA", "IL"])
    await db.flush()
    _zrows = (await db.execute(text("SELECT zip, id FROM zip_code"))).all()
    zmap = {z: i for z, i in _zrows}  # zip → zip_code.id

    # ── 2. 마스터 데이터 ──────────────────────────────────────
    banner("마스터 데이터")
    cust = CustomerModel(team_id=tid, name="ACME Importers", code="ACME", kind=PartnerKind.CUSTOMER,
                         contact_name="Amy Chen", contact_email="amy@acme.com", contact_phone="+1-213-555-0101",
                         billing_address="500 Cargo Way, Los Angeles, CA", payment_terms_days=30,
                         zip_id=zmap.get("90021"), created_by_user_id=aid)
    carrier = CustomerModel(team_id=tid, name="Blue Line Carrier", code="BLUE", kind=PartnerKind.CARRIER,
                            mc_number="MC-998877", dot_number="DOT-223344", insurance_expires_at=date(2027, 1, 31),
                            contact_email="ops@blueline.com", created_by_user_id=aid)
    broker = CustomerModel(team_id=tid, name="Pacific Broker Group", code="PBG", kind=PartnerKind.BROKER, created_by_user_id=aid)
    vendor = CustomerModel(team_id=tid, name="Yard Services Vendor", code="YSV", kind=PartnerKind.VENDOR, created_by_user_id=aid)
    db.add_all([cust, carrier, broker, vendor])
    await db.flush()

    term1 = TerminalModel(team_id=tid, name="APM Terminals Pier 400", code="APM4",
                          address="2500 Navy Way, San Pedro, CA", latitude=D("33.730"), longitude=D("-118.260"),
                          zip_id=zmap.get("90731"), created_by_user_id=aid)
    term2 = TerminalModel(team_id=tid, name="LBCT Long Beach", code="LBCT",
                          address="1521 Pier G Ave, Long Beach, CA", latitude=D("33.752"), longitude=D("-118.205"),
                          zip_id=zmap.get("90802"), created_by_user_id=aid)
    db.add_all([term1, term2])

    ves1 = VesselModel(team_id=tid, name="MAERSK ESSEX", imo_number="9456789", line="Maersk", created_by_user_id=aid)
    ves2 = VesselModel(team_id=tid, name="ONE TRIUMPH", imo_number="9789456", line="ONE", created_by_user_id=aid)
    db.add_all([ves1, ves2])

    loc_yard = LocationModel(team_id=tid, name="Carson Yard", kind=LocationKind.YARD,
                             address="18000 S Main St, Carson, CA", latitude=D("33.831"), longitude=D("-118.281"),
                             zip_id=zmap.get("90745"), created_by_user_id=aid)
    loc_cust = LocationModel(team_id=tid, name="ACME DC Fontana", kind=LocationKind.CUSTOMER,
                             address="15000 Valley Blvd, Fontana, CA", latitude=D("34.092"), longitude=D("-117.435"),
                             customer_id=cust.id, zip_id=zmap.get("92335"), created_by_user_id=aid)
    loc_port = LocationModel(team_id=tid, name="POLA Gate", kind=LocationKind.PORT,
                             latitude=D("33.742"), longitude=D("-118.272"), created_by_user_id=aid)
    loc_other = LocationModel(team_id=tid, name="Truck Wash Wilmington", kind=LocationKind.OTHER, created_by_user_id=aid)
    db.add_all([loc_yard, loc_cust, loc_port, loc_other])
    await db.flush()

    pool1 = EquipmentPoolModel(team_id=tid, name="TRAC Pool LA", kind=EquipmentPoolKind.THIRD_PARTY_POOL,
                               operator="TRAC Intermodal", location_id=loc_yard.id, created_by_user_id=aid)
    pool2 = EquipmentPoolModel(team_id=tid, name="APM Terminal Pool", kind=EquipmentPoolKind.TERMINAL_POOL,
                               operator="APM", location_id=loc_port.id, created_by_user_id=aid)
    db.add_all([pool1, pool2])
    await db.flush()

    # 드라이버 (user 링크) — default_truck/chassis 는 나중에 update (순환 FK)
    drivers = []
    for i, u in enumerate(duser, start=1):
        drv = DriverModel(
            team_id=tid, user_id=u.id, license_number=f"CDL-{1000 + i}", license_state="CA",
            duty_status=DutyStatus.ON_DUTY if i == 1 else DutyStatus.OFF_DUTY,
            employment_kind=EmploymentKind.IN_HOUSE if i < 3 else EmploymentKind.CARRIER_DRIVER,
            carrier_id=carrier.id if i == 3 else None,
            payment_terms_kind=PaymentTermsKind.PER_LEG if i < 3 else PaymentTermsKind.PERCENT_OF_REVENUE,
            payment_terms_value=D("150") if i < 3 else D("0.72"),
            license_expires_at=date(2028, 5, 31), hire_date=date(2024, 1, 15), created_by_user_id=aid,
        )
        db.add(drv)
        drivers.append(drv)
    await db.flush()

    trucks = [
        TruckModel(team_id=tid, plate_no=f"CA-TRK{100 + i}", vin=f"1FUJA6CV{i:06d}", make="Freightliner",
                   model="Cascadia", year=2022, owner_kind=TruckOwnerKind.COMPANY, status=TruckStatus.ACTIVE,
                   insurance_expires_at=date(2027, 3, 31), created_by_user_id=aid)
        for i in (1, 2, 3)
    ]
    db.add_all(trucks)
    await db.flush()

    chassis = [
        ChassisModel(team_id=tid, chassis_number=f"CHS-{200 + i}", size=ChassisSize.SIZE_40,
                     owner_kind=ChassisOwnerKind.THIRD_PARTY_POOL, owner_pool_id=pool1.id,
                     status=ChassisStatus.AVAILABLE, current_location_id=loc_yard.id, created_by_user_id=aid)
        for i in (1, 2, 3)
    ]
    db.add_all(chassis)
    await db.flush()

    # 순환 FK 마무리: 드라이버 기본 트럭/샤시
    for drv, trk, chs in zip(drivers, trucks, chassis):
        drv.default_truck_id = trk.id
        drv.default_chassis_id = chs.id
    await db.flush()
    print("  customer×4, terminal×2, vessel×2, location×4, pool×2, driver×3, truck×3, chassis×3")

    # ── 3. Add-on 마스터 (시스템 시드 + per-driver override) ───
    banner("Add-on 마스터")
    await AddonService(db, tid).seed_defaults(actor_user_id=aid)
    await db.flush()
    db.add(AddonModel(team_id=tid, code="FUEL", name="Fuel (Driver Override)", category=AddonCategory.FUEL,
                      unit=AddonUnit.PERCENT, percent=D("0.18"), driver_id=drivers[0].id,
                      is_billable_to_customer=True, is_payable_to_driver=True, created_by_user_id=aid))
    await db.flush()
    addon_ngt = (await db.execute(text(
        "SELECT id, code FROM addon WHERE team_id=:t AND code='NGT' AND driver_id IS NULL LIMIT 1"
    ), {"t": tid})).first()
    print("  addon seed_defaults + FUEL per-driver override")

    # ── 4. 요율 서브시스템 ────────────────────────────────────
    banner("요율 (rate_*)")
    # 재설계(Zone×Zone): SoCal 드레이 존 7개 (zip→zone 매핑). 항만 기준 거리지수(idx)로 가격 생성.
    def _zone(name, code, color, desc):
        z = RateZoneModel(team_id=tid, name=name, code=code, color=color,
                          description=desc, created_by_user_id=aid)
        db.add(z)
        return z

    z_port = _zone("Port / Harbor", "PORT", "#0ea5e9", "San Pedro / Long Beach 항만")
    z_la = _zone("Los Angeles", "LA", "#8b5cf6", "LA Basin / Commerce")
    z_oc = _zone("Orange County", "OC", "#f59e0b", "Anaheim / Santa Ana")
    z_ie = _zone("Inland Empire", "IE", "#3b82f6", "Fontana / Ontario / San Bernardino")
    z_ven = _zone("Ventura", "VEN", "#ec4899", "Oxnard / Ventura")
    z_hd = _zone("High Desert", "HD", "#a855f7", "Victorville / Hesperia")
    z_sd = _zone("San Diego", "SD", "#10b981", "San Diego 항만권")
    await db.flush()
    _members = {
        z_port: ["90731", "90802", "90744"],
        z_la: ["90001", "90021", "90040"],
        z_oc: ["92805", "92701"],
        z_ie: ["92335", "91761", "92408"],
        z_ven: ["93030", "93001"],
        z_hd: ["92392", "92345"],
        z_sd: ["92101", "92154"],
    }
    for _z, _zips in _members.items():
        for _zc in _zips:
            db.add(RateZoneMemberModel(team_id=tid, zone_id=_z.id, zip_code=_zc, created_by_user_id=aid))
    ZIDX = {z_port: 0, z_la: 25, z_oc: 35, z_ie: 60, z_ven: 65, z_hd: 95, z_sd: 120}
    ZONES = [z_port, z_la, z_oc, z_ie, z_ven, z_hd, z_sd]

    # 그룹 12개 — 방식(ZONE/CITY/MILE/HOURLY)별 3개씩
    def _grp(name, method, desc, default=False):
        g = RateGroupModel(team_id=tid, name=name, method=method, is_default=default,
                           description=desc, created_by_user_id=aid)
        db.add(g)
        return g

    grp_zone = _grp("Default ZONE Rates", RateMethod.ZONE, "기본 존간(from→to) 요율", default=True)
    grp_zone_rf = _grp("Reefer ZONE Rates", RateMethod.ZONE, "리퍼(냉동) 존간 할증")
    grp_zone_ow = _grp("Overweight ZONE Rates", RateMethod.ZONE, "오버웨이트 존간 할증")
    grp_city = _grp("City Rates — SoCal", RateMethod.CITY, "도시간 기본 요율")
    grp_city_ex = _grp("City Rates — Express", RateMethod.CITY, "도시간 익스프레스")
    grp_city_rf = _grp("City Rates — Reefer", RateMethod.CITY, "도시간 리퍼")
    grp_mile = _grp("Standard Mileage", RateMethod.MILE, "표준 마일 단가")
    grp_mile_pr = _grp("Premium Mileage", RateMethod.MILE, "프리미엄 마일 단가")
    grp_mile_lo = _grp("Local Mileage", RateMethod.MILE, "로컬 마일 단가")
    grp_hour = _grp("Standard Hourly", RateMethod.HOURLY, "표준 시간 단가")
    grp_hour_dt = _grp("Detention Hourly", RateMethod.HOURLY, "디텐션 시간 단가")
    grp_hour_tm = _grp("Team Driver Hourly", RateMethod.HOURLY, "팀 드라이버 시간 단가")
    await db.flush()

    # 멀티플라이어: 팀 전역(폴백) + Default ZONE 전용
    db.add_all([
        RateMultiplierModel(team_id=tid, rate_group_id=None, container_size=RateContainerSize.SIZE_20,
                            factor=D("0.85"), note="20ft 전역 할인", created_by_user_id=aid),
        RateMultiplierModel(team_id=tid, rate_group_id=None, container_size=RateContainerSize.SIZE_45,
                            factor=D("1.15"), note="45ft 전역 할증", created_by_user_id=aid),
        RateMultiplierModel(team_id=tid, rate_group_id=grp_zone.id, container_size=RateContainerSize.SIZE_20,
                            factor=D("0.80"), note="Default ZONE 20ft", created_by_user_id=aid),
        RateMultiplierModel(team_id=tid, rate_group_id=grp_zone.id, container_size=RateContainerSize.SIZE_45,
                            factor=D("1.20"), note="Default ZONE 45ft", created_by_user_id=aid),
    ])
    await db.flush()

    # ── 요율 셀: UI 와 동일한 RateGroupEntryService.set_entry 경로(시트 자동 생성/라우팅) ──
    rate_svc = RateGroupEntryService(db, tid)
    L, E = RateMoveType.LOAD, RateMoveType.EMPTY
    LV, DR = RateServiceType.LIVE, RateServiceType.DROP
    S40, S20 = RateContainerSize.SIZE_40, RateContainerSize.SIZE_20
    JAN = date(2026, 1, 1)

    def _round5(v):
        return str(int(round(v / 5.0) * 5))

    async def zcell(grp, mv, sv, fz, tz, size, amt, eff=JAN):
        await rate_svc.set_entry(grp.id, FlatRateEntryRequest(
            move_type=mv, service_type=sv, from_zone_id=fz.id, to_zone_id=tz.id,
            container_size=size, amount=D(amt), effective_from=eff), actor_user_id=aid)

    async def ccell(grp, mv, sv, fc, tc, size, amt, eff=JAN):
        await rate_svc.set_entry(grp.id, FlatRateEntryRequest(
            move_type=mv, service_type=sv, from_city=fc, from_state="CA", to_city=tc, to_state="CA",
            container_size=size, amount=D(amt), effective_from=eff), actor_user_id=aid)

    async def ucell(grp, per_unit, eff=JAN):
        await rate_svc.set_entry(grp.id, FlatRateEntryRequest(
            per_unit=D(per_unit), effective_from=eff), actor_user_id=aid)

    # 모든 (move, service) 9조합 × 모든 사이즈 → 어떤 선택이든 매트릭스가 꽉 차게.
    N_M, N_S = RateMoveType.NONE, RateServiceType.NONE
    S45 = RateContainerSize.SIZE_45
    ALL_COMBOS = [
        (L, LV, 1.00), (L, DR, 0.92), (L, N_S, 0.85),
        (E, LV, 0.55), (E, DR, 0.45), (E, N_S, 0.40),
        (N_M, LV, 0.35), (N_M, DR, 0.30), (N_M, N_S, 0.25),
    ]
    SIZES_F = [(S20, 0.85), (S40, 1.00), (S45, 1.15)]  # 사이즈별 배율

    async def fill_zone_matrix(grp, group_mult):
        """그룹의 모든 (move,service)×사이즈×from≠to 를 채움(완전 충진)."""
        for mv, sv, ms in ALL_COMBOS:
            for sz, sf in SIZES_F:
                for fz in ZONES:
                    for tz in ZONES:
                        if fz is tz:
                            continue
                        dist = abs(ZIDX[tz] - ZIDX[fz])
                        await zcell(grp, mv, sv, fz, tz, sz,
                                    _round5((90 + dist * 2.6) * group_mult * ms * sf))

    await fill_zone_matrix(grp_zone, 1.00)
    await fill_zone_matrix(grp_zone_rf, 1.40)
    await fill_zone_matrix(grp_zone_ow, 1.55)
    # PORT→IE LOAD/LIVE 40 = 285→310 버전 2개로 오버라이드(payroll/e2e 정합)
    await zcell(grp_zone, L, LV, z_port, z_ie, S40, "285")
    await zcell(grp_zone, L, LV, z_port, z_ie, S40, "310", eff=date(2026, 6, 1))

    # City 매트릭스 — 대표 도시 6개(zip 마스터 표기와 일치)
    CITIES = [("San Pedro", 0), ("Long Beach", 10), ("Los Angeles", 25),
              ("Anaheim", 35), ("Santa Ana", 40), ("Fontana", 60)]

    async def fill_city_matrix(grp, group_mult):
        for mv, sv, ms in ALL_COMBOS:
            for sz, sf in SIZES_F:
                for fc, fi in CITIES:
                    for tc, ti in CITIES:
                        if fc == tc:
                            continue
                        await ccell(grp, mv, sv, fc, tc, sz,
                                    _round5((95 + abs(ti - fi) * 3.0) * group_mult * ms * sf))

    await fill_city_matrix(grp_city, 1.00)
    await fill_city_matrix(grp_city_ex, 1.25)
    await fill_city_matrix(grp_city_rf, 1.40)

    # MILE / HOURLY per_unit (좌표 없는 단일 셀)
    await ucell(grp_mile, "2.75")
    await ucell(grp_mile_pr, "3.25")
    await ucell(grp_mile_lo, "2.40")
    await ucell(grp_hour, "85.00")
    await ucell(grp_hour_dt, "120.00")
    await ucell(grp_hour_tm, "150.00")

    # 드라이버 배정 — 방식 다양화 (driver0=ZONE 유지: payroll/e2e 정합)
    for _drv, _grp in [(drivers[0], grp_zone), (drivers[1], grp_mile), (drivers[2], grp_hour)]:
        db.add(DriverRateAssignmentModel(team_id=tid, driver_id=_drv.id, rate_group_id=_grp.id,
                                         effective_from=JAN, created_by_user_id=aid))
    await db.flush()
    print("  zone×7 + member×17, group×12 (ZONE/CITY/MILE/HOURLY 각 3), multiplier×4, "
          "rate_entry 5800+ (9 move×service × 3사이즈 × 전 from→to, 완전 충진), assignment×3")

    # ── 5. Load Type 템플릿 (시스템 시드) ─────────────────────
    banner("Load Type 템플릿")
    await LoadTypeTemplateService(db, tid).seed_defaults(actor_user_id=aid)
    await db.flush()
    print("  load_type_template + steps (시스템 시드)")

    # ── 6. D/O 워크플로우 ─────────────────────────────────────
    banner("D/O · 컨테이너 · Point · 이벤트")
    do_imp = DeliveryOrderModel(team_id=tid, customer_id=cust.id, direction=ShipmentDirection.IMPORT,
                                status=DeliveryStatus.DISPATCHED, bl_number="MAEU-1234567", booking_number="BK-IMP-001",
                                reference="PO-99001", terminal_id=term1.id, vessel_id=ves1.id, eta=NOW,
                                bl_released=True, internal_note="우선 처리", created_by_user_id=aid)
    do_exp = DeliveryOrderModel(team_id=tid, customer_id=cust.id, direction=ShipmentDirection.EXPORT,
                                status=DeliveryStatus.PLANNING, bl_number="ONEY-7654321", booking_number="BK-EXP-002",
                                terminal_id=term2.id, vessel_id=ves2.id, eta=NOW, created_by_user_id=aid)
    db.add_all([do_imp, do_exp])
    await db.flush()

    cont_imp = ContainerModel(team_id=tid, delivery_order_id=do_imp.id, sequence_no=1, container_number="MSCU1234567",
                              seal_no="SEAL-001", size=ContainerSize.SIZE_40HC, type="DRY", weight_kg=D("18500"),
                              chassis_id=chassis[0].id, service_type=ServiceType.LIVE, status=DeliveryStatus.DISPATCHED,
                              work_state=ContainerState.IN_TRANSIT, pier_pass_paid=True, customs_cleared=True,
                              delivery_location_id=loc_cust.id, return_location_id=loc_yard.id,
                              demurrage_lfd=date(2026, 6, 12), detention_lfd=date(2026, 6, 18), created_by_user_id=aid)
    cont_exp = ContainerModel(team_id=tid, delivery_order_id=do_exp.id, sequence_no=1, container_number="TCLU7654321",
                              size=ContainerSize.SIZE_20GP, type="DRY", weight_kg=D("12000"),
                              service_type=ServiceType.DROP, status=DeliveryStatus.PLANNING,
                              work_state=ContainerState.PLANNED, created_by_user_id=aid)
    db.add_all([cont_imp, cont_exp])
    await db.flush()

    # Point 시퀀스 (각 컨테이너 3 포인트 = 2 레그)
    def stops_for(cont, points):
        out = []
        for seq, (pt, kw) in enumerate(points, start=1):
            out.append(ContainerStopModel(team_id=tid, container_id=cont.id, sequence_no=seq, point_type=pt,
                                           planned_arrival=NOW, created_by_user_id=aid, **kw))
        return out

    imp_stops = stops_for(cont_imp, [
        (PointType.TERMINAL, {"terminal_id": term1.id}),
        (PointType.CUSTOMER, {"customer_id": cust.id, "location_id": loc_cust.id}),
        (PointType.YARD, {"location_id": loc_yard.id}),
    ])
    exp_stops = stops_for(cont_exp, [
        (PointType.YARD, {"location_id": loc_yard.id}),
        (PointType.CUSTOMER, {"customer_id": cust.id}),
        (PointType.TERMINAL, {"terminal_id": term2.id}),
    ])
    db.add_all([*imp_stops, *exp_stops])
    await db.flush()

    db.add_all([
        ContainerEventModel(team_id=tid, container_id=cont_imp.id, event_kind=ContainerEventKind.GATE_OUT,
                            location_id=loc_port.id, occurred_at=NOW, created_by_user_id=aid),
        ContainerEventModel(team_id=tid, container_id=cont_imp.id, event_kind=ContainerEventKind.DELIVERED,
                            location_id=loc_cust.id, occurred_at=NOW, created_by_user_id=aid),
    ])

    # ── 7. 레그 + add-on + segment ───────────────────────────
    banner("레그 · leg add-on · 세그먼트")

    def make_leg(do, cont, frm, to, mt, st, status, mc, completed=False, drv=None):
        return LegModel(
            team_id=tid, delivery_order_id=do.id, container_id=cont.id, step=DeliveryStatus.DISPATCHED,
            move_type=mt, service_type=st, from_point_id=frm.id, to_point_id=to.id,
            from_location_type=frm.point_type, to_location_type=to.point_type, move_code=mc,
            origin_zip="90731", origin_city="San Pedro", origin_state="CA",
            dest_zip="92335", dest_city="Fontana", dest_state="CA",
            rate_miles=D("58.0"), status=status, driver_id=(drv.id if drv else None),
            truck_id=(trucks[0].id if drv else None), chassis_id=cont.chassis_id,
            pickup_date=NOW, completed_at=(NOW if completed else None), is_settled=completed,
            created_by_user_id=aid,
        )

    leg_imp1 = make_leg(do_imp, cont_imp, imp_stops[0], imp_stops[1], MoveType.LOADED, ServiceType.LIVE,
                        LegStatus.COMPLETED, LegMoveCode.PPU, completed=True, drv=drivers[0])
    leg_imp2 = make_leg(do_imp, cont_imp, imp_stops[1], imp_stops[2], MoveType.EMPTY, ServiceType.DROP,
                        LegStatus.COMPLETED, LegMoveCode.PRE, completed=True, drv=drivers[0])
    leg_exp1 = make_leg(do_exp, cont_exp, exp_stops[0], exp_stops[1], MoveType.LOADED, ServiceType.LIVE,
                        LegStatus.PENDING, LegMoveCode.PPU)
    leg_exp2 = make_leg(do_exp, cont_exp, exp_stops[1], exp_stops[2], MoveType.EMPTY, ServiceType.NONE,
                        LegStatus.PENDING, LegMoveCode.PRE)
    db.add_all([leg_imp1, leg_imp2, leg_exp1, leg_exp2])
    await db.flush()

    # leg add-on: 일반(NGT) + EXTRA_STOP(STP, 위치형)
    db.add_all([
        LegAddonModel(team_id=tid, leg_id=leg_imp1.id, addon_id=(addon_ngt.id if addon_ngt else None),
                      code="NGT", quantity=D("1"), amount=D("50.00"),
                      is_payable_to_driver=True, is_billable_to_customer=True, created_by_user_id=aid),
        LegAddonModel(team_id=tid, leg_id=leg_imp1.id, code="STP", quantity=D("1"), amount=D("30.00"),
                      is_payable_to_driver=True, is_billable_to_customer=True,
                      point_type=PointType.CUSTOMER, customer_id=cust.id, location_id=loc_cust.id,
                      note="Extra stop at DC", created_by_user_id=aid),
    ])
    db.add(LegDriverSegmentModel(team_id=tid, leg_id=leg_imp1.id, sequence_no=1, driver_id=drivers[0].id,
                                 truck_id=trucks[0].id, started_at=NOW, ended_at=NOW,
                                 handover_reason=HandoverReason.SHIFT_CHANGE, created_by_user_id=aid))
    db.add(ChassisEventModel(team_id=tid, chassis_id=chassis[0].id, leg_id=leg_imp1.id,
                             event_kind=ChassisEventKind.PICKED_UP, location_id=loc_port.id,
                             occurred_at=NOW, created_by_user_id=aid))
    # D/O 단위 add-on (고객 청구)
    db.add(DeliveryOrderAddonModel(team_id=tid, delivery_order_id=do_imp.id, code="DMR", quantity=D("2"),
                                   unit_amount=D("125.00"), amount=D("250.00"), is_payable_to_driver=False,
                                   is_billable_to_customer=True, note="Demurrage 2 days", created_by_user_id=aid))
    await db.flush()
    print("  leg×4(2완료/2대기), leg_addon×2, segment×1, chassis_event×1, do_addon×1, container_event×2")

    # ── 8. Street turn / Dual transaction ─────────────────────
    banner("Street Turn · Dual Transaction")
    db.add(StreetTurnModel(team_id=tid, import_order_id=do_imp.id, export_order_id=do_exp.id,
                           container_id=cont_imp.id, container_number=cont_imp.container_number,
                           link_type=StreetTurnLinkType.MANUAL, status=StreetTurnStatus.APPROVED,
                           carrier_approval_no="ST-APPR-001", requested_by=aid, requested_at=NOW,
                           approved_by=aid, approved_at=NOW, created_by_user_id=aid))
    db.add(DualTransactionModel(team_id=tid, driver_id=drivers[0].id, truck_id=trucks[0].id,
                                return_leg_id=leg_imp2.id, pickup_leg_id=leg_exp1.id,
                                status=DualTransactionStatus.PLANNED, scheduled_at=NOW, created_by_user_id=aid))
    await db.flush()

    # ── 9. 정산 · 청구 ────────────────────────────────────────
    banner("Payroll · Invoice")
    settle = PayrollSettlementModel(team_id=tid, driver_id=drivers[0].id, period_start=date(2026, 6, 1),
                                    period_end=date(2026, 6, 14), status=PayrollStatus.CONFIRMED,
                                    base_total=D("570.00"), addon_total=D("80.00"), grand_total=D("650.00"),
                                    note="격주 정산", created_by_user_id=aid)
    db.add(settle)
    await db.flush()
    db.add_all([
        # leg_imp1(LOADED/LIVE, port→IE) work_date 2026-06-09 → 유효요율 310(2026-06-01부) 과 일치.
        PayrollLineModel(team_id=tid, settlement_id=settle.id, leg_id=leg_imp1.id, work_date=date(2026, 6, 9),
                         base_amount=D("310.00"), source=PayrollLineSource.RESOLVED, created_by_user_id=aid),
        # leg_imp2(EMPTY/DROP) 는 해당 시트 미존재 → 실제 정산이면 unresolved. 데모용 수기값.
        PayrollLineModel(team_id=tid, settlement_id=settle.id, leg_id=leg_imp2.id, work_date=date(2026, 6, 9),
                         base_amount=D("180.00"), source=PayrollLineSource.MANUAL, created_by_user_id=aid),
    ])
    db.add_all([
        PayrollChargeModel(team_id=tid, settlement_id=settle.id, addon_id=(addon_ngt.id if addon_ngt else None),
                           code="NGT", quantity=D("1"), amount=D("50.00"), note="leg #1 NGT", created_by_user_id=aid),
        PayrollChargeModel(team_id=tid, settlement_id=settle.id, code="STP", quantity=D("1"), amount=D("30.00"),
                           note="leg #1 STP", created_by_user_id=aid),
    ])

    inv = InvoiceModel(team_id=tid, customer_id=cust.id, delivery_order_id=do_imp.id, invoice_number="INV-2026-001",
                       status=InvoiceStatus.ISSUED, issue_date=date(2026, 6, 10), due_date=date(2026, 7, 10),
                       cost_total=D("650.00"), charge_total=D("950.00"), note="원가+마진", created_by_user_id=aid)
    db.add(inv)
    await db.flush()
    db.add_all([
        InvoiceLineModel(team_id=tid, invoice_id=inv.id, container_id=cont_imp.id, description="Drayage MSCU1234567",
                         quantity=D("1"), unit_amount=D("650.00"), amount=D("650.00"), source=InvoiceLineSource.PREFILL,
                         cost_amount=D("570.00"), created_by_user_id=aid),
        InvoiceLineModel(team_id=tid, invoice_id=inv.id, description="Demurrage (2 days)", quantity=D("2"),
                         unit_amount=D("150.00"), amount=D("300.00"), source=InvoiceLineSource.MANUAL, created_by_user_id=aid),
    ])
    await db.flush()
    print("  settlement(line×2, charge×2), invoice(line×2)")

    # ── 10. 모바일 · 실시간 · 기타 ────────────────────────────
    banner("모바일 · 알림 · 감사 · API · 파일")
    db.add_all([
        LocationPingModel(team_id=tid, driver_id=drivers[0].id, latitude=D("33.7401"), longitude=D("-118.2710"),
                          speed_kmh=D("65.0"), heading_deg=D("90.0"), accuracy_m=D("5.0"), occurred_at=NOW, created_by_user_id=aid),
        LocationPingModel(team_id=tid, driver_id=drivers[0].id, latitude=D("33.8200"), longitude=D("-118.0500"),
                          speed_kmh=D("0.0"), occurred_at=NOW, created_by_user_id=aid),
        LocationPingModel(team_id=tid, driver_id=drivers[1].id, latitude=D("33.7520"), longitude=D("-118.2050"),
                          speed_kmh=D("40.0"), occurred_at=NOW, created_by_user_id=aid),
    ])
    db.add_all([
        NotificationModel(team_id=tid, user_id=dispatcher.id, channel=NotificationChannel.PUSH,
                          status=NotificationStatus.SENT, event_type="leg.completed", title="Leg 완료",
                          body="Leg #1 이 완료되었습니다.", is_read=False, sent_at=NOW, created_by_user_id=aid),
        NotificationModel(team_id=tid, user_id=admin.id, channel=NotificationChannel.EMAIL,
                          status=NotificationStatus.DELIVERED, event_type="invoice.issued", title="인보이스 발행",
                          body="INV-2026-001 발행됨.", is_read=True, read_at=NOW, sent_at=NOW, created_by_user_id=aid),
    ])
    db.add_all([
        ChatMessageModel(team_id=tid, driver_user_id=duser[0].id, sender_type=ChatSenderType.DISPATCHER,
                         sender_user_id=dispatcher.id, content="픽업 준비됐나요?", created_by_user_id=aid),
        ChatMessageModel(team_id=tid, driver_user_id=duser[0].id, sender_type=ChatSenderType.DRIVER,
                         sender_user_id=duser[0].id, content="네, 터미널 도착했습니다.", read_at=NOW, created_by_user_id=aid),
    ])
    db.add_all([
        AuditLogModel(team_id=tid, entity_type="delivery_order", entity_id=do_imp.id, action="status_changed",
                      summary="PLANNING → DISPATCHED", before_state={"status": "PLANNING"},
                      after_state={"status": "DISPATCHED"}, created_by_user_id=aid),
        AuditLogModel(team_id=tid, entity_type="invoice", entity_id=inv.id, action="issued",
                      summary="INV-2026-001 발행", created_by_user_id=aid),
    ])
    db.add(ApiKeyModel(team_id=tid, name="Default Integration Key", description="외부 통합용",
                       key="tmsk_" + "0" * 40, prefix="tmsk_0000", created_by_user_id=aid))
    db.add_all([
        FileAssetModel(domain=FileDomain.TEAM, object_id=tid, subdir="logo", filename="logo.png", size=20480,
                       mime="image/png", is_public=True, logical_path=f"team/{tid}/logo/logo.png",
                       team_id=tid, created_by_user_id=aid),
        FileAssetModel(domain=FileDomain.LEG_DOCUMENT, object_id=leg_imp1.id, subdir="pod", filename="pod_signed.pdf",
                       size=102400, mime="application/pdf", is_public=False,
                       logical_path=f"leg/{leg_imp1.id}/pod/pod_signed.pdf", team_id=tid, created_by_user_id=aid),
    ])
    # push_token (ORM 모델 있음 — registry import 로 등록됨)
    for i, drv in enumerate(drivers):
        db.add(PushTokenModel(team_id=tid, driver_id=drv.id, platform="fcm",
                              token=f"fcmtoken_{drv.id}_{i}", last_used_at=NOW, created_by_user_id=aid))
    await db.flush()
    await db.commit()
    print("  location_ping×3, notification×2, chat×2, audit_log×2, api_key×1, file_asset×2, push_token×3")


async def verify(db: AsyncSession):
    """alembic_version 제외 전 테이블 COUNT≥1 단언 + 로그인 검증."""
    banner("VERIFY — 전수 단언")
    names = [r[0] for r in (await db.execute(text("SHOW TABLES"))).all() if r[0] != "alembic_version"]
    empty = []
    total = 0
    for n in names:
        c = (await db.execute(text(f"SELECT COUNT(*) FROM `{n}`"))).scalar() or 0
        total += c
        if c == 0:
            empty.append(n)
    print(f"  테이블 {len(names)}개, 총 {total} 행")
    if empty:
        print(f"  ❌ 빈 테이블 {len(empty)}개: {', '.join(empty)}")
    else:
        print(f"  ✅ 빈 테이블 0개 — 모든 테이블에 데이터 존재")

    # 로그인 검증
    row = (await db.execute(text("SELECT password, role FROM user WHERE email=:e"), {"e": LOGIN_EMAIL})).first()
    ok = bool(row) and bcrypt.checkpw(LOGIN_PW.encode(), row[0].encode())
    print(f"  로그인 {LOGIN_EMAIL}/{LOGIN_PW}: {'✅ OK' if ok else '❌ FAIL'} (role={row[1] if row else '?'})")
    return not empty and ok


async def main():
    try:
        async with AsyncSession(write_engine, expire_on_commit=False) as db:
            await wipe(db)
            await seed(db)
            ok = await verify(db)
        banner("DONE" if ok else "DONE (경고: 위 실패 확인)")
        print(f"로그인: {LOGIN_EMAIL} / {LOGIN_PW}\n")
    finally:
        await write_engine.dispose()  # aiomysql 커넥션 정리(이벤트 루프 경고 방지)


if __name__ == "__main__":
    asyncio.run(main())
