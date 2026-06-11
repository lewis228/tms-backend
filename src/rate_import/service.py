# src/rate_import/service.py
"""요율 CSV import/export 어댑터 (model 없음).

ste 규약: 다른 도메인 Repository 직접 주입(서비스→서비스 호출 지양).
- 셀 import: RateSheetRepository + versioning.set_rate
- Zone 멤버 import: RateZoneRepository.replace_members
- export: 각 repo 의 list_* 로 CSV 직렬화

⚠️ 후속 보강(설계문서 명시): openpyxl 기반 .xlsx 템플릿(매트릭스 시트 + Flat_All),
   import batch 이력/롤백, 지도 폴리곤 → zip 백필(shapely + zip centroid dataset).
"""
from __future__ import annotations
import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from rate_sheet.repository import RateSheetRepository
from rate_sheet import versioning
from rate_sheet.const.status import RateEntrySource, RateMoveType, RateServiceType
from rate_zone.repository import RateZoneRepository
from rate_import.schemas.response import CsvImportReport, ImportRowError

_ENTRY_HEADER = ["from_zip", "to_zip", "from_zone_id", "to_zone_id",
                 "from_city", "from_state", "to_city", "to_state",
                 "amount", "per_unit", "effective_from"]
# 그룹 단위 플랫 행 표준: move/service 컬럼 포함. 좌표는 양방향(↔) — 순서 무관.
_GROUP_HEADER = ["move_type", "service_type", "from_zip", "to_zip",
                 "from_zone_id", "to_zone_id",
                 "from_city", "from_state", "to_city", "to_state",
                 "amount", "per_unit", "effective_from"]
_MEMBER_HEADER = ["zip_code", "city", "state"]


def _opt_int(v: str | None):
    v = (v or "").strip()
    return int(v) if v else None


def _opt_dec(v: str | None):
    v = (v or "").strip()
    if not v:
        return None
    try:
        return Decimal(v)
    except InvalidOperation:
        raise ValueError(f"숫자 형식 오류: '{v}'")


class RateImportService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.sheet_repo = RateSheetRepository(db, team_id)
        self.zone_repo = RateZoneRepository(db, team_id)

    # ── 셀(rate_entry) import ───────────────────────────────────
    def _parse_entries(self, csv_text: str) -> Tuple[List[dict], List[ImportRowError]]:
        rows: List[dict] = []
        errors: List[ImportRowError] = []
        reader = csv.DictReader(io.StringIO(csv_text))
        for i, raw in enumerate(reader, start=1):
            try:
                eff = (raw.get("effective_from") or "").strip()
                if not eff:
                    raise ValueError("effective_from 필수")
                amount = _opt_dec(raw.get("amount"))
                per_unit = _opt_dec(raw.get("per_unit"))
                if amount is None and per_unit is None:
                    raise ValueError("amount 또는 per_unit 필요")
                rows.append({
                    "cell": {
                        "from_zip": (raw.get("from_zip") or "").strip() or None,
                        "to_zip": (raw.get("to_zip") or "").strip() or None,
                        "from_zone_id": _opt_int(raw.get("from_zone_id")),
                        "to_zone_id": _opt_int(raw.get("to_zone_id")),
                        "from_city": (raw.get("from_city") or "").strip() or None,
                        "from_state": (raw.get("from_state") or "").strip() or None,
                        "to_city": (raw.get("to_city") or "").strip() or None,
                        "to_state": (raw.get("to_state") or "").strip() or None,
                    },
                    "amount": amount, "per_unit": per_unit,
                    "effective_from": date.fromisoformat(eff),
                })
            except ValueError as e:
                errors.append(ImportRowError(row=i, message=str(e)))
        return rows, errors

    async def import_sheet_entries(self, sheet_id: int, csv_text: str, dry_run: bool, actor_user_id: int | None) -> CsvImportReport:
        sheet = await self.sheet_repo.get_sheet(sheet_id)
        if not sheet:
            raise NotFoundException("Rate Sheet")
        rows, errors = self._parse_entries(csv_text)
        if errors:
            return CsvImportReport(ok=False, total=len(rows) + len(errors), applied=0, dry_run=dry_run, errors=errors)
        if dry_run:
            return CsvImportReport(ok=True, total=len(rows), applied=0, dry_run=True)
        for r in rows:
            await versioning.set_rate(
                self.sheet_repo, sheet_id, r["cell"],
                amount=r["amount"], per_unit=r["per_unit"],
                effective_from=r["effective_from"], source=RateEntrySource.IMPORT,
                reason="CSV import", actor_user_id=actor_user_id,
            )
        return CsvImportReport(ok=True, total=len(rows), applied=len(rows), dry_run=False)

    async def export_sheet_entries(self, sheet_id: int) -> str:
        sheet = await self.sheet_repo.get_sheet(sheet_id)
        if not sheet:
            raise NotFoundException("Rate Sheet")
        entries = await self.sheet_repo.list_entries(sheet_id, only_open=True)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(_ENTRY_HEADER)
        for e in entries:
            w.writerow([
                e.from_zip or "", e.to_zip or "",
                e.from_zone_id or "", e.to_zone_id or "", e.from_city or "", e.from_state or "",
                e.to_city or "", e.to_state or "",
                e.amount if e.amount is not None else "", e.per_unit if e.per_unit is not None else "",
                e.effective_from.isoformat(),
            ])
        return buf.getvalue()

    # ── 그룹 단위 플랫 행 import/export (move/service 포함) ──────
    def _parse_group_rows(self, csv_text: str):
        """플랫 CSV → List[FlatRateEntryRequest], errors. (lazy import 로 순환참조 회피)"""
        from rate_group.schemas.request import FlatRateEntryRequest
        rows = []
        errors: List[ImportRowError] = []
        reader = csv.DictReader(io.StringIO(csv_text))
        for i, raw in enumerate(reader, start=1):
            try:
                eff = (raw.get("effective_from") or "").strip()
                if not eff:
                    raise ValueError("effective_from 필수")
                mv = (raw.get("move_type") or "").strip() or None
                sv = (raw.get("service_type") or "").strip() or None
                rows.append(FlatRateEntryRequest(
                    move_type=RateMoveType(mv) if mv else None,
                    service_type=RateServiceType(sv) if sv else None,
                    from_zip=(raw.get("from_zip") or "").strip() or None,
                    to_zip=(raw.get("to_zip") or "").strip() or None,
                    from_zone_id=_opt_int(raw.get("from_zone_id")),
                    to_zone_id=_opt_int(raw.get("to_zone_id")),
                    from_city=(raw.get("from_city") or "").strip() or None,
                    from_state=(raw.get("from_state") or "").strip() or None,
                    to_city=(raw.get("to_city") or "").strip() or None,
                    to_state=(raw.get("to_state") or "").strip() or None,
                    amount=_opt_dec(raw.get("amount")),
                    per_unit=_opt_dec(raw.get("per_unit")),
                    effective_from=date.fromisoformat(eff),
                    source=RateEntrySource.IMPORT,
                    reason="CSV import",
                ))
            except (ValueError, KeyError) as e:
                errors.append(ImportRowError(row=i, message=str(e)))
        return rows, errors

    async def import_group_entries(self, group_id: int, csv_text: str, dry_run: bool, actor_user_id: int | None) -> CsvImportReport:
        from rate_group.entry_service import RateGroupEntryService
        rows, errors = self._parse_group_rows(csv_text)
        if errors:
            return CsvImportReport(ok=False, total=len(rows) + len(errors), applied=0, dry_run=dry_run, errors=errors)
        if dry_run:
            return CsvImportReport(ok=True, total=len(rows), applied=0, dry_run=True)
        svc = RateGroupEntryService(self.db, self.team_id)
        for row in rows:
            await svc.set_entry(group_id, row, actor_user_id=actor_user_id)
        return CsvImportReport(ok=True, total=len(rows), applied=len(rows), dry_run=False)

    async def export_group_entries(self, group_id: int) -> str:
        from rate_group.entry_service import RateGroupEntryService
        resp = await RateGroupEntryService(self.db, self.team_id).list_entries(group_id)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(_GROUP_HEADER)
        for r in resp.rows:
            w.writerow([
                r.move_type.value if r.move_type else "", r.service_type.value if r.service_type else "",
                r.from_zip or "", r.to_zip or "",
                r.from_zone_id or "", r.to_zone_id or "", r.from_city or "", r.from_state or "",
                r.to_city or "", r.to_state or "",
                r.amount if r.amount is not None else "", r.per_unit if r.per_unit is not None else "",
                r.effective_from.isoformat(),
            ])
        return buf.getvalue()

    # ── Zone 멤버(zip/city) import ──────────────────────────────
    def _parse_members(self, csv_text: str) -> Tuple[List[dict], List[ImportRowError]]:
        rows: List[dict] = []
        errors: List[ImportRowError] = []
        reader = csv.DictReader(io.StringIO(csv_text))
        for i, raw in enumerate(reader, start=1):
            zip_code = (raw.get("zip_code") or "").strip() or None
            city = (raw.get("city") or "").strip() or None
            state = (raw.get("state") or "").strip() or None
            if bool(zip_code) == bool(city):
                errors.append(ImportRowError(row=i, message="zip_code 또는 (city,state) 중 정확히 하나 필요"))
                continue
            if city and not state:
                errors.append(ImportRowError(row=i, message="city 멤버는 state 가 필요합니다"))
                continue
            rows.append({"zip_code": zip_code, "city": city, "state": state})
        return rows, errors

    async def import_zone_members(self, zone_id: int, csv_text: str, dry_run: bool, actor_user_id: int | None) -> CsvImportReport:
        zone = await self.zone_repo.get_header(zone_id)
        if not zone:
            raise NotFoundException("Rate Zone")
        rows, errors = self._parse_members(csv_text)
        if errors:
            return CsvImportReport(ok=False, total=len(rows) + len(errors), applied=0, dry_run=dry_run, errors=errors)
        if dry_run:
            return CsvImportReport(ok=True, total=len(rows), applied=0, dry_run=True)
        await self.zone_repo.replace_members(zone_id, rows, actor_user_id=actor_user_id)
        return CsvImportReport(ok=True, total=len(rows), applied=len(rows), dry_run=False)

    async def export_zone_members(self, zone_id: int) -> str:
        zone = await self.zone_repo.get_header(zone_id)
        if not zone:
            raise NotFoundException("Rate Zone")
        members = await self.zone_repo.list_members(zone_id)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(_MEMBER_HEADER)
        for m in members:
            w.writerow([m.zip_code or "", m.city or "", m.state or ""])
        return buf.getvalue()
