# src/team/repository.py
from __future__ import annotations
from typing import List, Optional, Iterable, Dict

from sqlalchemy import select, func, delete, update, text
from sqlalchemy.orm import selectinload, load_only, with_loader_criteria
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime
from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.service import CommonService

from rbac.model import PermissionGroupModel, PermissionGroupPermission, PermissionModel
from team.model import TeamModel, UserTeamModel
from user.model import UserModel
from team.schemas.request import PaginateTeamMemberRequestSchema, PaginateTeamRequestSchema

class TeamRepository:
    # 레포지토리 초기화: 세션/공통 페이지네이션 서비스 바인딩
    def __init__(self, db: AsyncSession):
        self.db = db
        self.common = CommonService()

    # ───────────────────────────────────────────────────────────────
    # 목록 전용 로딩 옵션 — 현재는 상세와 동일(추후 쉽게 경량화)
    # ───────────────────────────────────────────────────────────────
    #
    # [리스트 경량화 시 반드시 같이 바꿀 것 — 3-셋트 규칙]
    # 1) Response Schema (TeamListItemResponseSchema)
    #    - 리스트에서 안 보낼 관계/필드는 스키마에서 아예 제거하세요.
    #      * 스키마에서 필드를 지우면 Pydantic(from_attributes=True)가 해당
    #        관계에 접근하지 않아 lazy='raise' 환경에서도 안전합니다.
    #      * 점진 전환이 필요하면 Optional[...] | None = None 으로 한시 유지 후 최종 제거.
    #
    # 2) Repository (_with_options_list)
    #    - 스키마에서 제거한 관계의 selectinload(...), with_loader_criteria(...)
    #      를 동일하게 제거하세요. (불필요 쿼리/왕복 감소)
    #
    # 3) Service
    #    - 수동 변환은 지양합니다.
    #      result.data = [TeamListItemResponseSchema.model_validate(r) for r in result.data]
    #      같은 직변환 패턴을 유지하세요.
    #
    # [주의: Lazy 정책]
    # - 스키마에 필드가 남아 있는데 레포에서 관계를 로드하지 않으면,
    #   Pydantic 접근 시 lazy 로딩이 발생합니다(lazy="raise"면 예외).
    #   ⇒ 스키마와 레포 로딩 옵션을 항상 일치시키세요.
    #
    # [프론트 영향]
    # - 목록 응답에서 제거된 필드는 더 이상 기대하면 안 됩니다.
    #   (필요시 상세 API에서 가져오도록 UX 조정)
    # - 단계적 제거 시 null/빈배열 처리 방침을 프론트와 합의.
    #
    # [빠른 적용 예시]
    # - 스키마: TeamListItemResponseSchema에서 불필요 필드 제거
    # - 레포: 아래 selectinload(...) 및 관련 with_loader_criteria(...) 제거
    # - 서비스: 변경 없음(직변환 유지)
    # ───────────────────────────────────────────────────────────────

    # 상세 조회용 로딩 옵션을 stmt에 적용(팀 기본 컬럼 + 설정 컬럼 + 활성 멤버 최소 컬럼 로드)
    def _with_options_detail(self, stmt):
        return stmt.options(
            load_only(
                TeamModel.id,
                TeamModel.name,
                # 온보딩 상태 컬럼
                TeamModel.onboarding_step1_done,
                TeamModel.onboarding_step2_done,
                TeamModel.onboarding_step3_done,
                TeamModel.onboarding_completed,
                # 팀 설정 컬럼
                TeamModel.memo,
                TeamModel.timezone,
                TeamModel.image_url,
                TeamModel.company_name,
                TeamModel.registration_number,
                TeamModel.address,
                TeamModel.representative_name,
                TeamModel.phone_number,
                TeamModel.currency,
                TeamModel.decimal_places,
                TeamModel.product_info_display,
                TeamModel.product_info_template,
                TeamModel.excel_product_identification,
                TeamModel.gs1_gtin_enabled,
            ),
            # Team → members (활성만)
            selectinload(TeamModel.members)
                .load_only(
                    UserTeamModel.id,
                    UserTeamModel.user_id,
                    UserTeamModel.permission_group_id,
                ),
            with_loader_criteria(UserTeamModel, UserTeamModel.is_active.is_(True), include_aliases=True),
            # Team → files (이미지 등)
            selectinload(TeamModel.files),
        )

    # 목록 조회용 로딩 옵션을 stmt에 적용(현재 상세와 동일)
    def _with_options_list(self, stmt):
        return stmt.options(
            load_only(
                TeamModel.id,
                TeamModel.name,
                # 온보딩 상태 컬럼
                TeamModel.onboarding_step1_done,
                TeamModel.onboarding_step2_done,
                TeamModel.onboarding_step3_done,
                TeamModel.onboarding_completed,
            ),
            # (현재는 상세와 동일) Team → members (활성만)
            selectinload(TeamModel.members)
                .load_only(
                    UserTeamModel.id,
                    UserTeamModel.user_id,
                    UserTeamModel.permission_group_id,
                ),
            with_loader_criteria(UserTeamModel, UserTeamModel.is_active.is_(True), include_aliases=True),
            # 팀 이미지 파일
            selectinload(TeamModel.files),
        )

    # ─────────────────────────────────────────────
    # 로딩 옵션: 팀 멤버 목록 전용 (NEW)
    # ─────────────────────────────────────────────
    #
    # - UserTeamModel 자체의 최소 컬럼 + 중첩 user/permission_group의 최소 컬럼만 로드
    # - 서비스는 ORM을 그대로 UserTeamResponseSchema로 직변환(from_attributes=True)

    # 멤버 목록용 로딩 옵션을 stmt에 적용(유저/권한그룹 최소 컬럼만)
    def _with_options_members(self, stmt):
        return stmt.options(
            load_only(
                UserTeamModel.id,
                UserTeamModel.team_id,
                UserTeamModel.user_id,
                UserTeamModel.permission_group_id,
            ),
            # 유저: 목록에 필요한 최소 컬럼 + 프로필 이미지(files)
            selectinload(UserTeamModel.user).load_only(
                UserModel.id,
                UserModel.email,
                UserModel.role,
                UserModel.name,
            ).selectinload(UserModel.files),
            # 권한 그룹: 목록에 필요한 최소 컬럼만
            selectinload(UserTeamModel.permission_group).load_only(
                PermissionGroupModel.id,
                PermissionGroupModel.name,
            ),
        )

    # team_id로 활성 팀 단건 조회(활성 멤버 로딩 포함)
    async def get_team(self, team_id: int) -> Optional[TeamModel]:
        """활성 팀 단일 조회"""
        stmt = (
            select(TeamModel)
            .where(TeamModel.id == team_id, TeamModel.is_active.is_(True))
        )
        stmt = self._with_options_detail(stmt)
        return await self.db.scalar(stmt)

    # team_id로 비활성 포함 팀 단건 조회(삭제/복구 등의 내부용)
    async def get_team_including_inactive(self, team_id: int) -> Optional[TeamModel]:
        """비활성 포함 단일 조회(삭제/복구 등 내부 용도)
        — load_only 없이 전체 컬럼 로드 (deferred 접근 greenlet 방지)
        — 관계(members, files)는 로드하지 않음
        """
        stmt = select(TeamModel).where(TeamModel.id == team_id)
        return await self.db.scalar(stmt)

    # 팀 생성(INSERT 후 flush/refresh로 PK 확보)
    async def create_team(self, *, name: str) -> TeamModel:
        team = TeamModel(name=name)
        self.db.add(team)
        await self.db.flush()
        await self.db.refresh(team)
        return team

    # 팀 이름 변경(UPDATE)
    async def rename_team(self, team_id: int, *, name: str) -> None:
        await self.db.execute(
            update(TeamModel).where(TeamModel.id == team_id).values(name=name)
        )

    # 팀 하드 삭제 — 모든 팀 스코프 데이터 물리 삭제
    async def hard_delete_team(self, team_id: int) -> None:
        """물리 삭제 — 팀 스코프 데이터 전체 삭제

        team_id FK(CASCADE)만으로는 도메인 테이블 간 composite FK(RESTRICT)가
        삭제 순서를 블로킹하므로, FK_CHECKS=0 상태에서 모든 팀 스코프 테이블을
        명시적으로 삭제한 뒤 팀 행을 제거한다.

        테이블 목록은 Base.metadata에서 자동 수집하므로 새 도메인 추가 시
        별도 수정이 필요 없다.
        """
        from common.model.team_scoped_mixin import get_team_scoped_table_names

        await self.db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        try:
            for tbl in get_team_scoped_table_names():
                await self.db.execute(
                    text(f"DELETE FROM `{tbl}` WHERE team_id = :tid"),
                    {"tid": team_id},
                )
            # 팀 자체 삭제
            await self.db.execute(
                text("DELETE FROM `teams` WHERE id = :tid"),
                {"tid": team_id},
            )
        finally:
            await self.db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    # 특정 사용자(user_id)가 속한 활성 팀 목록 조회(정렬 포함)
    async def fetch_user_team(self, user_id: int) -> List[TeamModel]:
        """
        사용자 소속 + 활성 팀 목록
        - members 컬렉션은 관계에서 order_by 안정 정렬됨
        - 멤버 컬렉션은 활성만 로드(with_loader_criteria)
        """
        stmt = (
            select(TeamModel)
            .join(UserTeamModel, UserTeamModel.team_id == TeamModel.id)
            .where(UserTeamModel.user_id == user_id, TeamModel.is_active.is_(True))
        )
        stmt = self._with_options_list(stmt).order_by(TeamModel.name.asc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # 팀 멤버 수 집계(count)
    async def count_team_members(self, team_id: int) -> int:
        q = select(func.count(UserTeamModel.user_id)).where(UserTeamModel.team_id == team_id)
        return (await self.db.execute(q)).scalar_one()

    # 팀 내 관리자 그룹 멤버 수
    async def count_admin_members(self, team_id: int) -> int:
        stmt = (
            select(func.count(UserTeamModel.user_id))
            .select_from(UserTeamModel)
            .join(PermissionGroupModel, PermissionGroupModel.id == UserTeamModel.permission_group_id)
            .where(
                UserTeamModel.team_id == team_id,
                UserTeamModel.is_active.is_(True),
                PermissionGroupModel.is_admin.is_(True),
                PermissionGroupModel.is_active.is_(True),
            )
        )
        return (await self.db.execute(stmt)).scalar_one()

    # 특정 멤버가 관리자 그룹에 속하는지 여부
    async def is_admin_member(self, team_id: int, user_id: int) -> bool:
        stmt = (
            select(func.count())
            .select_from(UserTeamModel)
            .join(PermissionGroupModel, PermissionGroupModel.id == UserTeamModel.permission_group_id)
            .where(
                UserTeamModel.team_id == team_id,
                UserTeamModel.user_id == user_id,
                UserTeamModel.is_active.is_(True),
                PermissionGroupModel.is_admin.is_(True),
                PermissionGroupModel.is_active.is_(True),
            )
        )
        return (await self.db.execute(stmt)).scalar_one() > 0

    # 특정 user가 해당 팀의 멤버인지 여부(bool)
    async def is_member(self, team_id: int, user_id: int) -> bool:
        stmt = select(func.count()).select_from(UserTeamModel).where(
            UserTeamModel.team_id == team_id,
            UserTeamModel.user_id == user_id,
        )
        return (await self.db.execute(stmt)).scalar_one() > 0

    # 팀에 멤버 추가(권한 그룹 id 옵션)
    async def add_member(self, *, team_id: int, user_id: int, permission_group_id: Optional[int]) -> None:
        self.db.add(UserTeamModel(
            user_id=user_id,
            team_id=team_id,
            permission_group_id=permission_group_id,
        ))
        await self.db.flush()

    async def get_active_member_user_ids(self, team_id: int) -> list[int]:
        """팀의 활성 멤버 user_id 목록 조회."""
        rows = await self.db.execute(
            select(UserTeamModel.user_id).where(
                UserTeamModel.team_id == team_id,
                UserTeamModel.is_active.is_(True),
            )
        )
        return [row[0] for row in rows.all()]

    # 팀에서 멤버 제거(단일 삭제)
    async def remove_member(self, *, team_id: int, user_id: int) -> None:
        await self.db.execute(
            delete(UserTeamModel).where(
                UserTeamModel.team_id == team_id,
                UserTeamModel.user_id == user_id,
            )
        )

    # ── 팀 설정 업데이트 ─────────────────────────────────────────────
    async def update_settings(self, team_id: int, update_data: dict) -> None:
        """전달된 필드만 UPDATE"""
        if not update_data:
            return
        await self.db.execute(
            update(TeamModel).where(TeamModel.id == team_id).values(**update_data)
        )

    # ── 팀 사용량 통계 ───────────────────────────────────────────────
    async def get_usage_stats(self, team_id: int) -> dict:
        """팀 사용량 통계 조회 (product, member, location counts)"""
        from product.model import ProductModel
        from location.model import LocationModel

        product_count = (await self.db.execute(
            select(func.count(ProductModel.id)).where(
                ProductModel.team_id == team_id,
                ProductModel.is_active.is_(True),
            )
        )).scalar_one()

        member_count = (await self.db.execute(
            select(func.count(UserTeamModel.id)).where(
                UserTeamModel.team_id == team_id,
                UserTeamModel.is_active.is_(True),
            )
        )).scalar_one()

        location_count = (await self.db.execute(
            select(func.count(LocationModel.id)).where(
                LocationModel.team_id == team_id,
                LocationModel.is_active.is_(True),
            )
        )).scalar_one()

        return {
            "product_count": product_count,
            "product_limit": 50000,
            "member_count": member_count,
            "member_limit": 100,
            "location_count": location_count,
            "location_limit": 100,
        }

    # ── RBAC 유틸 (팀 생성 시 기본 그룹 만들 때 사용) ─────────────────

    # 권한 그룹 생성(팀 스코프)
    async def create_group(
        self, *, team_id: int, name: str,
        is_admin: bool = False,
        is_system: bool = False,
        system_key: Optional[str] = None,
    ) -> PermissionGroupModel:
        grp = PermissionGroupModel(
            team_id=team_id, name=name,
            is_admin=is_admin,
            is_system=is_system,
            system_key=system_key,
        )
        self.db.add(grp)
        await self.db.flush()
        await self.db.refresh(grp)
        return grp

    # 모든 권한 코드 → id 매핑 딕셔너리 획득
    async def get_permission_id_map(self) -> Dict[str, int]:
        rows = await self.db.execute(select(PermissionModel.code, PermissionModel.id))
        return {code: pid for code, pid in rows.all()}

    # 권한 그룹에 다수의 permission_id 매핑 레코드 삽입(중복 제거 후 일괄 flush)
    async def add_permissions_to_group(
        self, *, team_id: int, group_id: int, permission_ids: Iterable[int]
    ) -> None:
        """
        팀 스코프 테이블(permission_group_permissions)에 INSERT 시
        team_id가 반드시 필요함. (NOT NULL + (team_id, group_id) FK)
        """
        grp = await self.db.get(PermissionGroupModel, group_id)
        if not grp:
            raise ValueError(f"group not found: {group_id}")
        if grp.team_id != team_id:
            raise ValueError(f"team mismatch: group.team_id={grp.team_id} vs arg team_id={team_id}")

        rows = []
        for pid in set(permission_ids):
            rows.append(PermissionGroupPermission(
                team_id=team_id,
                group_id=group_id,
                permission_id=pid,
            ))
        if rows:
            self.db.add_all(rows)
            await self.db.flush()

    # ── 커서 페이지네이션: 내 팀 목록 ────────────────────────────────
    # 해당 user_id가 속한 활성 팀 목록을 커서 페이지네이션으로 조회
    async def list_my_teams_paginated(
        self,
        user_id: int,
        request: PaginateTeamRequestSchema,
    ) -> CursorPaginationResult[TeamModel]:
        base = (
            select(TeamModel)
            .join(UserTeamModel, UserTeamModel.team_id == TeamModel.id)
            .where(
                UserTeamModel.user_id == user_id,
                TeamModel.is_active.is_(True),
            )
        )
        base = self._with_options_list(base)

        result = await self.common.paginate(
            request=request,
            model=TeamModel,
            session=self.db,
            base_query=base,
            path="team/my-teams/cursor",
        )
        return result

    # ── 커서 페이지네이션: 멤버 목록 ─────────────────────────────────
    # 특정 팀의 활성 멤버(UserTeam) 목록을 커서 페이지네이션으로 조회
    async def list_members_paginated(
        self,
        *,
        team_id: int,
        request: PaginateTeamMemberRequestSchema,
    ) -> CursorPaginationResult[UserTeamModel]:
        """
        팀 멤버(유저-팀 조인) 목록을 커서 페이지네이션으로 반환.
        - base 쿼리에서 user_team.is_active=True만 선택
        - 관계 로딩은 selectinload + load_only로 최소 컬럼 명시
        - 여기서는 ORM 그대로 반환(가공 X) → 서비스에서 UserTeamResponseSchema로 직변환
        """
        common = CommonService()

        base = (
            select(UserTeamModel)
            .where(
                UserTeamModel.team_id == team_id,
                UserTeamModel.is_active.is_(True),
            )
        )
        base = self._with_options_members(base)

        result = await common.paginate(
            request=request,
            model=UserTeamModel,
            session=self.db,
            base_query=base,
            path=f"team/{team_id}/members",
        )
        return result

    # ── Delta Sync: 멤버 목록 (hard-delete → all_ids) ──────────────
    async def sync_members_delta(self, team_id: int, since: datetime):
        """
        since 이후 변경된 활성 멤버 + 전체 활성 멤버 ID (hard-delete 도메인)
        """
        common = CommonService()
        base = (
            select(UserTeamModel)
            .where(UserTeamModel.team_id == team_id)
        )
        base = self._with_options_members(base)

        return await common.sync_delta(
            model=UserTeamModel,
            session=self.db,
            since=since,
            team_id=team_id,
            base_query=base,
            use_soft_delete=False,
        )
