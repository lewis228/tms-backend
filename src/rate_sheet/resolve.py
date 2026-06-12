# src/rate_sheet/resolve.py
"""요율 종합 해석 엔진 — driver → 그룹 체인 → 해석 사다리 → 단가 산출.

payroll/invoice 가 정산·청구 시점에 사용. payroll.resolve.resolve_leg_rate 가 leg 의
(driver, work_date, move_type, origin/dest zip·city, miles/hours) 를
뽑아 이 RateResolver.resolve 를 호출하고, 결과 base 를 payroll_line 에 snapshot 동결한다.

해석 사다리 (컨플루언스 v12 — 셀은 전부 양방향 ↔):
  [배정된 그룹 안에서]
  ① 원자↔원자 (zip↔zip / city↔city)   match_step=ATOM_ATOM
  ② 원자↔존   (어느 쪽이 원자든 동일)   match_step=ATOM_ZONE
  ③ 존↔존                              match_step=ZONE_ZONE
  [전부 실패하면]
  ④ 디폴트 그룹의 ①~③ — 배정 그룹이 상속형 커스텀(inherits_default)일 때
  ⑤ UNRESOLVED (found=False)
기사 미배정 시 ZIP 방식 디폴트 그룹으로 폴백(assignment_fallback=True).
존 조회는 그룹 스코프 존 > 글로벌 존.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from rate_sheet.repository import RateSheetRepository, _CELL_KEYS
from rate_sheet import lookup
from rate_sheet.lane import normalize_cell
from rate_sheet.const.status import SheetKind, RateMoveType, RateServiceType
from rate_sheet.schemas.response import RateResolveResultSchema
from rate_group.repository import RateGroupRepository
from rate_group.const.status import RateMethod
from rate_zone.repository import RateZoneRepository
from zip_code.repository import ZipCodeRepository
from driver_rate_assignment.service import DriverRateAssignmentService


def _fail(msg: str, **kw) -> RateResolveResultSchema:
    return RateResolveResultSchema(found=False, message=msg, **kw)


def _empty_cell() -> dict:
    return {k: None for k in _CELL_KEYS}


class RateResolver:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.sheet_repo = RateSheetRepository(db, team_id)
        self.group_repo = RateGroupRepository(db, team_id)
        self.zone_repo = RateZoneRepository(db, team_id)
        self.zip_repo = ZipCodeRepository(db)
        self.dra_svc = DriverRateAssignmentService(db, team_id)

    async def resolve(
        self, *, driver_id: int | None, work_date: date,
        move_type: RateMoveType | None = None,
        service_type: RateServiceType | None = None,
        from_zip: str | None = None, from_city: str | None = None, from_state: str | None = None,
        dest_zip: str | None = None, dest_city: str | None = None, dest_state: str | None = None,
        miles: Decimal | None = None, hours: Decimal | None = None,
    ) -> RateResolveResultSchema:
        # 1) 드라이버 → 그룹 (배정 없음/기사 미지정이면 ZIP 디폴트 그룹 폴백 — 설계 §9)
        #    driver_id=None 은 디스패처 조회 화면의 "기사 미선택" 케이스.
        assignment_fallback = False
        assign = (
            await self.dra_svc.get_active_for_driver(driver_id, work_date)
            if driver_id is not None else None
        )
        if assign is not None:
            group = await self.group_repo.get(assign.rate_group_id)
            if group is None:
                return _fail("배정된 요율그룹이 비활성/삭제되었습니다.", rate_group_id=assign.rate_group_id)
        else:
            group = await self.group_repo.get_default_for_method(RateMethod.ZIP)
            if group is None:
                who = f"드라이버(id={driver_id}) 의 {work_date.isoformat()} 기준 요율그룹 배정이 없고" \
                    if driver_id is not None else "기사 미지정 조회인데"
                return _fail(f"{who} ZIP 방식 디폴트 그룹도 없습니다.")
            assignment_fallback = True

        # 2) 그룹 체인 — 배정 그룹 → (상속형 커스텀이면) 같은 방식의 디폴트 그룹 (사다리 ④)
        chain = [group]
        if not group.is_default and group.inherits_default:
            dg = await self.group_repo.get_default_for_method(group.method)
            if dg is not None and dg.id != group.id:
                chain.append(dg)
        method = group.method

        # 3) method 분기
        if method in (RateMethod.MILE, RateMethod.HOURLY):
            return await self._resolve_unit(chain, method, work_date,
                                            miles=miles, hours=hours,
                                            assignment_fallback=assignment_fallback)
        return await self._resolve_matrix(chain, method, work_date,
                                          move_type=move_type, service_type=service_type,
                                          from_zip=from_zip, from_city=from_city, from_state=from_state,
                                          dest_zip=dest_zip, dest_city=dest_city, dest_state=dest_state,
                                          assignment_fallback=assignment_fallback)

    # ── MILE / HOURLY — per_unit 단일 셀 (상속 폴백 대칭 적용) ──────────
    async def _resolve_unit(
        self, chain, method: RateMethod, work_date: date, *,
        miles: Decimal | None, hours: Decimal | None, assignment_fallback: bool,
    ) -> RateResolveResultSchema:
        kind = SheetKind.MILE if method == RateMethod.MILE else SheetKind.HOURLY
        qty = miles if method == RateMethod.MILE else hours
        if qty is None:
            # 0 으로 치환해 "조용한 $0.00 성공"을 만들지 않는다 — 미해석(found=False)으로
            # 올려 payroll 이 UNRESOLVED 로 잡게 한다 (매트릭스 분기의 입력 가드와 대칭).
            need = "miles" if method == RateMethod.MILE else "hours"
            return _fail(f"{method.value} 해석에는 {need} 가 필요합니다.",
                         method=method.value, rate_group_id=chain[0].id)
        last_fail_kw: dict = {"method": method.value, "rate_group_id": chain[0].id}
        for idx, g in enumerate(chain):
            sheet = await self.sheet_repo.find_slot(g.id, kind, None)
            if sheet is None:
                continue
            lk = await lookup.resolve_cell(self.sheet_repo, sheet.id, _empty_cell(), work_date)
            if lk.found and lk.per_unit is not None:
                base = (lk.per_unit * qty).quantize(Decimal("0.01"))
                return RateResolveResultSchema(
                    found=True, method=method.value, rate_group_id=g.id, rate_sheet_id=sheet.id,
                    rate_entry_id=lk.rate_entry_id, per_unit=lk.per_unit, quantity=qty, base_amount=base,
                    match_step="UNIT", via_default_group=(idx > 0),
                    assignment_fallback=assignment_fallback,
                    effective_from=lk.effective_from, effective_to=lk.effective_to,
                )
            last_fail_kw["rate_sheet_id"] = sheet.id
        return _fail(f"{method.value} 단가 미등록 (사다리 ④까지 미해석).", **last_fail_kw)

    # ── ZIP / CITY — 양방향 사다리 ①~③ × 그룹 체인 ─────────────────────
    async def _resolve_matrix(
        self, chain, method: RateMethod, work_date: date, *,
        move_type: RateMoveType | None, service_type: RateServiceType | None,
        from_zip: str | None, from_city: str | None, from_state: str | None,
        dest_zip: str | None, dest_city: str | None, dest_state: str | None,
        assignment_fallback: bool,
    ) -> RateResolveResultSchema:
        gid0 = chain[0].id
        if move_type is None:
            return _fail("ZIP/CITY 해석에는 move_type 이 필요합니다.", method=method.value, rate_group_id=gid0)
        kind = SheetKind.ZIP if method == RateMethod.ZIP else SheetKind.CITY

        # 원자 결정 — ZIP: zip 쌍 필수 / CITY: city 없으면 zip 마스터에서 파생
        if method == RateMethod.ZIP:
            if not from_zip or not dest_zip:
                return _fail("ZIP 해석에는 from_zip 과 dest_zip 이 모두 필요합니다.",
                             method=method.value, rate_group_id=gid0)
        else:
            if not from_city and from_zip:
                z = await self.zip_repo.get_by_zip(from_zip)
                if z:
                    from_city, from_state = z.city, z.state
            if not dest_city and dest_zip:
                z = await self.zip_repo.get_by_zip(dest_zip)
                if z:
                    dest_city, dest_state = z.city, z.state
            if not from_city or not dest_city:
                return _fail("CITY 해석에는 from_city 와 dest_city 가 모두 필요합니다 (zip 파생 실패).",
                             method=method.value, rate_group_id=gid0)

        last_fail_kw: dict = {"method": method.value, "rate_group_id": gid0}
        for idx, g in enumerate(chain):
            # service_type 별 요율 우선, 없으면 service_type 무관(NULL) 슬롯 폴백 (기존 유지).
            sheet = await self.sheet_repo.find_slot(g.id, kind, move_type, service_type=service_type)
            if sheet is None and service_type is not None:
                sheet = await self.sheet_repo.find_slot(g.id, kind, move_type, service_type=None)
            if sheet is None:
                continue
            last_fail_kw["rate_sheet_id"] = sheet.id

            # 원자→존 (그룹 스코프 존 > 글로벌 존)
            if method == RateMethod.ZIP:
                f_zone = await self.zone_repo.resolve_zone_id_for_zip(from_zip, g.id)
                t_zone = await self.zone_repo.resolve_zone_id_for_zip(dest_zip, g.id)
                f_atom = {"from_zip": from_zip}
                t_atom = {"to_zip": dest_zip}
            else:
                f_zone = await self.zone_repo.resolve_zone_id_for_city(from_city, from_state, g.id)
                t_zone = await self.zone_repo.resolve_zone_id_for_city(dest_city, dest_state, g.id)
                f_atom = {"from_city": from_city, "from_state": from_state}
                t_atom = {"to_city": dest_city, "to_state": dest_state}

            # 사다리 후보 — 양방향이므로 모든 후보를 normalize 후 단일 조회.
            # 후보마다 "매칭에 실제 사용된 존"을 함께 들고 간다 — 성공 스냅샷의 zone_id 가
            # match_step 과 모순되지 않도록 (①원자↔원자=None, ②=해당 존, ③=dest 존).
            candidates: list[tuple[str, dict, int | None]] = []

            def _cell(f_part: dict, t_part: dict) -> dict:
                c = _empty_cell()
                c.update(f_part)
                c.update(t_part)
                return normalize_cell(c)

            candidates.append(("ATOM_ATOM", _cell(f_atom, t_atom), None))                          # ①
            if t_zone is not None:
                candidates.append(("ATOM_ZONE", _cell(f_atom, {"to_zone_id": t_zone}), t_zone))    # ② 원자↔존
            if f_zone is not None:
                candidates.append(("ATOM_ZONE", _cell({"from_zone_id": f_zone}, t_atom), f_zone))  # ② 존↔원자(동단계)
            if f_zone is not None and t_zone is not None:
                candidates.append(("ZONE_ZONE",
                                   _cell({"from_zone_id": f_zone}, {"to_zone_id": t_zone}),
                                   t_zone))                                                        # ③

            seen: set[tuple] = set()
            for step, coord, matched_zone_id in candidates:
                key = tuple(coord.get(k) for k in _CELL_KEYS)
                if key in seen:
                    continue
                seen.add(key)
                lk = await lookup.resolve_cell(self.sheet_repo, sheet.id, coord, work_date)
                if lk.found and lk.amount is not None:
                    return RateResolveResultSchema(
                        found=True, method=method.value, rate_group_id=g.id, rate_sheet_id=sheet.id,
                        rate_entry_id=lk.rate_entry_id, zone_id=matched_zone_id,
                        amount=lk.amount, base_amount=lk.amount.quantize(Decimal("0.01")),
                        match_step=step, via_default_group=(idx > 0),
                        assignment_fallback=assignment_fallback,
                        effective_from=lk.effective_from, effective_to=lk.effective_to,
                    )

        return _fail(
            f"요율 미해석(UNRESOLVED): 사다리 ①~④ 모두 불일치 (date={work_date.isoformat()}).",
            **last_fail_kw,
        )
